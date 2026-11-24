#!/usr/bin/env python3
"""Script 1: Synthesize chapter scripts via TTSProvider, master audio, and write audio_timeline.json."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from providers.registry import TTS_PROVIDERS, get_tts_provider

_ROMAN_REGNAL_MAP: dict[str, str] = {
    "I": "the First",
    "II": "the Second",
    "III": "the Third",
    "IV": "the Fourth",
    "V": "the Fifth",
    "VI": "the Sixth",
    "VII": "the Seventh",
    "VIII": "the Eighth",
    "IX": "the Ninth",
    "X": "the Tenth",
    "XI": "the Eleventh",
    "XII": "the Twelfth",
    "XIII": "the Thirteenth",
    "XIV": "the Fourteenth",
    "XV": "the Fifteenth",
    "XVI": "the Sixteenth",
}


def normalize_text_for_speech(text: str) -> str:
    """Expand common abbreviations and regnal numerals for cleaner TTS pronunciation."""
    out = text
    out = re.sub(r"\b(\d+)\s*BCE\b", r"\1 B.C.E.", out)
    out = re.sub(r"\b(\d+)\s*CE\b", r"\1 C.E.", out)
    out = re.sub(r"\b(\d+)\s*BC\b", r"\1 B.C.", out)
    out = re.sub(r"\bAD\s*(\d+)\b", r"A.D. \1", out)
    out = re.sub(r"\bc\.\s*(\d+)", r"circa \1", out)
    out = re.sub(r"\bSt\.\s+", "Saint ", out)

    def _replace_regnal(match: re.Match[str]) -> str:
        name, numeral = match.group(1), match.group(2)
        spoken = _ROMAN_REGNAL_MAP.get(numeral)
        return f"{name} {spoken}" if spoken else match.group(0)

    out = re.sub(
        r"\b(Henry|Louis|Charles|Edward|George|Philip|Richard|William|James|Elizabeth|Frederick|Alexander|Constantine|Pope\s+[A-Z][a-z]+)\s+(XVI|XV|XIV|XIII|XII|XI|IX|VIII|VII|VI|IV|III|II|X|V)\b",
        _replace_regnal,
        out,
    )
    return out


def parse_chapter_markdown(md_path: Path, fallback_num: int) -> tuple[int, str, str]:
    """Read chapter_XX.md -> (chapter_number, title, spoken_body)."""
    raw = md_path.read_text(encoding="utf-8").strip()
    lines = raw.splitlines()
    title = md_path.stem.replace("_", " ").title()
    num_match = re.search(r"(\d+)", md_path.stem)
    chapter_num = int(num_match.group(1)) if num_match else fallback_num

    idx = 0
    if lines and lines[0].startswith("#"):
        header = lines[0].lstrip("#").strip()
        header = re.sub(r"^Chapter\s+\d+\s*[:—-]\s*", "", header, flags=re.IGNORECASE)
        if header:
            title = header
        idx = 1
    while idx < len(lines) and not lines[idx].strip():
        idx += 1

    body = "\n".join(lines[idx:]).strip()
    return chapter_num, title, body


def probe_duration(path: Path) -> float:
    """Return media duration in seconds via ffprobe."""
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(json.loads(proc.stdout)["format"]["duration"])


def _generate_silence(output_wav: Path, duration: float, sample_rate: int = 44100) -> Path:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r={sample_rate}:cl=stereo",
            "-t",
            f"{duration:.3f}",
            "-c:a",
            "pcm_s16le",
            str(output_wav),
        ],
        check=True,
        capture_output=True,
    )
    return output_wav


def _master_voice(input_wav: Path, output_wav: Path, sample_rate: int = 44100) -> Path:
    """Normalize voice audio to consistent -16 LUFS broadcast loudness without clipping."""
    filter_chain = (
        "highpass=f=65,"
        "acompressor=threshold=-20dB:ratio=2.2:attack=25:release=220,"
        "alimiter=limit=0.89,"
        "loudnorm=I=-16:TP=-1.5:LRA=7"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_wav),
            "-af",
            filter_chain,
            "-ar",
            str(sample_rate),
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(output_wav),
        ],
        check=True,
        capture_output=True,
    )
    return output_wav


def _generate_ambience(
    output_wav: Path,
    duration: float,
    mode: str,
    sample_rate: int = 44100,
) -> Path:
    fade_out_start = max(0.0, duration - 4.0)
    if mode == "soft_rain":
        source = f"anoisesrc=color=pink:r={sample_rate}:d={duration:.3f}"
        af = (
            "highpass=f=180,lowpass=f=1400,tremolo=f=0.12:d=0.15,"
            f"afade=t=in:st=0:d=3,afade=t=out:st={fade_out_start:.3f}:d=4"
        )
    else:
        source = f"anoisesrc=color=brown:r={sample_rate}:d={duration:.3f}"
        af = (
            "highpass=f=45,lowpass=f=380,"
            f"afade=t=in:st=0:d=3,afade=t=out:st={fade_out_start:.3f}:d=4"
        )

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            source,
            "-af",
            af,
            "-ac",
            "2",
            "-ar",
            str(sample_rate),
            "-c:a",
            "pcm_s16le",
            str(output_wav),
        ],
        check=True,
        capture_output=True,
    )
    return output_wav


def _mix_ambience(
    narration_wav: Path,
    ambient_wav: Path,
    output_wav: Path,
    ambience_db: float,
) -> Path:
    filter_complex = (
        f"[1:a]volume={ambience_db:.1f}dB[amb];"
        "[0:a][amb]amix=inputs=2:duration=first:dropout_transition=3:normalize=0,"
        "alimiter=limit=0.92[out]"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(narration_wav),
            "-i",
            str(ambient_wav),
            "-filter_complex",
            filter_complex,
            "-map",
            "[out]",
            "-c:a",
            "pcm_s16le",
            str(output_wav),
        ],
        check=True,
        capture_output=True,
    )
    return output_wav


def run(
    run_dir: Path,
    *,
    provider_name: str | None = None,
    voice: str | None = None,
    voice_style: str | None = None,
    only_chapter: int | None = None,
    force: bool = False,
    ambience: str = "none",
    ambience_db: float = -28.0,
    intro_silence: float = 1.5,
    chapter_pause: float = 2.5,
    outro_silence: float = 3.0,
) -> dict:
    run_root = run_dir.resolve()
    script_dir = run_root / "02_script"
    audio_dir = run_root / "03_audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    chapter_files = sorted(script_dir.glob("chapter_*.md"))
    if not chapter_files:
        raise FileNotFoundError(f"No chapter_*.md files found in {script_dir}")

    tts = get_tts_provider(provider_name, voice=voice)

    intro_wav = _generate_silence(audio_dir / "_silence_intro.wav", intro_silence)
    pause_wav = _generate_silence(audio_dir / "_silence_chapter.wav", chapter_pause)
    outro_wav = _generate_silence(audio_dir / "_silence_outro.wav", outro_silence)

    concat_segments: list[Path] = [intro_wav]
    timeline_chapters: list[dict] = []
    cursor = intro_silence

    for idx, md_path in enumerate(chapter_files, start=1):
        ch_num, title, body = parse_chapter_markdown(md_path, fallback_num=idx)
        raw_wav = audio_dir / f"chapter_{ch_num:02d}_raw.wav"
        master_wav = audio_dir / f"chapter_{ch_num:02d}_master.wav"

        should_synth = force or (only_chapter == ch_num) or (only_chapter is None and not raw_wav.exists())
        if should_synth:
            print(f"[tts] Synthesizing Chapter {ch_num}: {title}")
            spoken = normalize_text_for_speech(body)
            tts.synthesize_to_wav(
                text=spoken,
                output_wav_path=raw_wav,
                voice=voice,
                style_instructions=voice_style,
            )
            _master_voice(raw_wav, master_wav)
        elif not master_wav.exists():
            _master_voice(raw_wav, master_wav)
        else:
            print(f"[tts] Reusing existing audio for Chapter {ch_num}: {title}")

        dur = probe_duration(master_wav)
        start_s = cursor
        end_s = cursor + dur
        timeline_chapters.append(
            {
                "chapter_number": ch_num,
                "title": title,
                "word_count": len(body.split()),
                "raw_audio_file": raw_wav.relative_to(run_root).as_posix(),
                "master_audio_file": master_wav.relative_to(run_root).as_posix(),
                "start_seconds": round(start_s, 3),
                "end_seconds": round(end_s, 3),
                "duration_seconds": round(dur, 3),
            }
        )
        concat_segments.append(master_wav)
        cursor = end_s

        if idx < len(chapter_files):
            concat_segments.append(pause_wav)
            cursor += chapter_pause

    concat_segments.append(outro_wav)

    concat_list = audio_dir / "_concat_audio.txt"
    concat_list.write_text(
        "\n".join(f"file '{p.resolve().as_posix()}'" for p in concat_segments),
        encoding="utf-8",
    )
    stitched_wav = audio_dir / "_narration_stitched.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c:a",
            "pcm_s16le",
            str(stitched_wav),
        ],
        check=True,
        capture_output=True,
    )

    stitched_dur = probe_duration(stitched_wav)
    final_master = audio_dir / "narration_master.wav"
    ambient_rel: str | None = None

    if ambience != "none":
        ambient_wav = audio_dir / "ambient_bed.wav"
        _generate_ambience(ambient_wav, stitched_dur + 1.0, mode=ambience)
        _mix_ambience(stitched_wav, ambient_wav, final_master, ambience_db=ambience_db)
        ambient_rel = ambient_wav.relative_to(run_root).as_posix()
    else:
        final_master.write_bytes(stitched_wav.read_bytes())

    timeline = {
        "master_audio_file": final_master.relative_to(run_root).as_posix(),
        "ambient_bed_file": ambient_rel,
        "total_duration_seconds": round(probe_duration(final_master), 3),
        "chapters": timeline_chapters,
    }
    timeline_path = audio_dir / "audio_timeline.json"
    timeline_path.write_text(json.dumps(timeline, indent=2) + "\n", encoding="utf-8")
    print(
        f"[tts] Wrote {final_master.relative_to(run_root)} "
        f"({timeline['total_duration_seconds']:.2f}s) and {timeline_path.relative_to(run_root)}"
    )
    return timeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthesize chapters and master narration audio.")
    parser.add_argument("run_dir", type=Path, help="Path to runs/<slug> directory.")
    parser.add_argument("--provider", choices=TTS_PROVIDERS, default=None, help="TTS provider override.")
    parser.add_argument("--voice", default=None, help="Optional voice name override.")
    parser.add_argument("--voice-style", default=None, help="Optional delivery style instructions.")
    parser.add_argument("--chapter", type=int, default=None, help="Regenerate only this chapter number.")
    parser.add_argument("--force", action="store_true", help="Re-synthesize all chapters.")
    parser.add_argument(
        "--ambience",
        choices=("none", "brown_noise", "soft_rain"),
        default="none",
        help="Optional procedural background bed.",
    )
    parser.add_argument("--ambience-db", type=float, default=-28.0, help="Ambience mix level in dB.")
    parser.add_argument("--intro-silence", type=float, default=1.5)
    parser.add_argument("--chapter-pause", type=float, default=2.5)
    parser.add_argument("--outro-silence", type=float, default=3.0)
    args = parser.parse_args()

    run(
        args.run_dir,
        provider_name=args.provider,
        voice=args.voice,
        voice_style=args.voice_style,
        only_chapter=args.chapter,
        force=args.force,
        ambience=args.ambience,
        ambience_db=args.ambience_db,
        intro_silence=args.intro_silence,
        chapter_pause=args.chapter_pause,
        outro_silence=args.outro_silence,
    )


if __name__ == "__main__":
    main()
