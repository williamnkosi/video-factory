"""Stage 3: Speech normalization, TTS synthesis, sleep audio mastering, and ambient mixing."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from video_factory.agents.prompts import NARRATOR_VOICE_INSTRUCTIONS
from video_factory.config import Settings
from video_factory.models import (
    AudioTimeline,
    ChapterAudioTiming,
    ProjectManifest,
    ScriptBundle,
)
from video_factory.providers.base import TTSProvider
from video_factory.storage import ProjectStore

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
    """Clean historical abbreviations and royal numerals for smoother TTS pronunciation."""
    out = text
    out = re.sub(r"\b(\d+)\s*BCE\b", r"\1 B.C.E.", out)
    out = re.sub(r"\b(\d+)\s*CE\b", r"\1 C.E.", out)
    out = re.sub(r"\b(\d+)\s*BC\b", r"\1 B.C.", out)
    out = re.sub(r"\bAD\s*(\d+)\b", r"A.D. \1", out)
    out = re.sub(r"\bc\.\s*(\d+)", r"circa \1", out)
    out = re.sub(r"\bSt\.\s+", "Saint ", out)

    # Convert common monarch regnal numerals like "Louis XIV" -> "Louis the Fourteenth"
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


def probe_media_duration(path: Path) -> float:
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
    payload = json.loads(proc.stdout)
    return float(payload["format"]["duration"])


def generate_silence_wav(output_wav: Path, duration_seconds: float, sample_rate: int = 44100) -> Path:
    """Generate clean stereo silent WAV segment via FFmpeg."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r={sample_rate}:cl=stereo",
            "-t",
            f"{duration_seconds:.3f}",
            "-c:a",
            "pcm_s16le",
            str(output_wav),
        ],
        check=True,
        capture_output=True,
    )
    return output_wav


def master_narration_wav(input_wav: Path, output_wav: Path, sample_rate: int = 44100) -> Path:
    """Apply sleep-safe warm EQ, gentle compression, limiter, and -16 LUFS normalization."""
    filter_chain = (
        "highpass=f=65,"
        "treble=g=-3:f=5200,"
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


def generate_ambient_bed(
    output_wav: Path,
    duration_seconds: float,
    mode: str = "brown_noise",
    sample_rate: int = 44100,
) -> Path:
    """Procedurally generate a soothing royalty-free ambient soundscape via FFmpeg."""
    if mode == "soft_rain":
        # Pink noise shaped with band-pass and slow gentle volume undulations resembling distant rain
        source = f"anoisesrc=color=pink:r={sample_rate}:d={duration_seconds:.3f}"
        af = (
            "highpass=f=180,lowpass=f=1400,"
            "tremolo=f=0.12:d=0.15,"
            f"afade=t=in:st=0:d=3,afade=t=out:st={max(0.0, duration_seconds - 4.0):.3f}:d=4"
        )
    else:
        # Warm, cozy low-frequency brown noise bed
        source = f"anoisesrc=color=brown:r={sample_rate}:d={duration_seconds:.3f}"
        af = (
            "highpass=f=45,lowpass=f=380,"
            f"afade=t=in:st=0:d=3,afade=t=out:st={max(0.0, duration_seconds - 4.0):.3f}:d=4"
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


def mix_narration_and_ambience(
    narration_wav: Path,
    ambient_wav: Path,
    output_wav: Path,
    ambience_volume_db: float = -28.0,
) -> Path:
    """Blend subtle ambient bed underneath mastered narration without clipping."""
    filter_complex = (
        f"[1:a]volume={ambience_volume_db:.1f}dB[amb];"
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


def run_narrator_agent(
    manifest: ProjectManifest,
    script_bundle: ScriptBundle,
    store: ProjectStore,
    tts: TTSProvider,
    settings: Settings,
    *,
    only_chapter: int | None = None,
) -> AudioTimeline:
    """Synthesize chapters, master for sleep comfort, stitch with pauses, and mix ambience."""
    store.audio_dir.mkdir(parents=True, exist_ok=True)
    chapter_timings: list[ChapterAudioTiming] = []
    concat_segments: list[Path] = []

    intro_wav = store.audio_dir / "_silence_intro.wav"
    pause_wav = store.audio_dir / "_silence_chapter.wav"
    outro_wav = store.audio_dir / "_silence_outro.wav"

    generate_silence_wav(intro_wav, settings.intro_silence_seconds)
    generate_silence_wav(pause_wav, settings.chapter_pause_seconds)
    generate_silence_wav(outro_wav, settings.outro_silence_seconds)

    cursor = settings.intro_silence_seconds
    concat_segments.append(intro_wav)

    for idx, chapter in enumerate(script_bundle.chapters):
        raw_wav = store.audio_dir / f"chapter_{chapter.chapter_number:02d}_raw.wav"
        master_wav = store.audio_dir / f"chapter_{chapter.chapter_number:02d}_master.wav"

        should_synth = (
            only_chapter is None
            or only_chapter == chapter.chapter_number
            or not raw_wav.exists()
        )
        if should_synth:
            spoken_text = normalize_text_for_speech(chapter.edited_text)
            tts.synthesize_to_wav(
                text=spoken_text,
                output_wav_path=raw_wav,
                voice_instructions=NARRATOR_VOICE_INSTRUCTIONS,
            )
            master_narration_wav(raw_wav, master_wav)
        elif not master_wav.exists():
            master_narration_wav(raw_wav, master_wav)

        dur = probe_media_duration(master_wav)
        start_s = cursor
        end_s = cursor + dur
        chapter_timings.append(
            ChapterAudioTiming(
                chapter_number=chapter.chapter_number,
                title=chapter.title,
                raw_audio_file=store.relative_str(raw_wav),
                master_audio_file=store.relative_str(master_wav),
                start_seconds=round(start_s, 3),
                end_seconds=round(end_s, 3),
                duration_seconds=round(dur, 3),
            )
        )
        concat_segments.append(master_wav)
        cursor = end_s

        if idx < len(script_bundle.chapters) - 1:
            concat_segments.append(pause_wav)
            cursor += settings.chapter_pause_seconds

    concat_segments.append(outro_wav)

    # Stitch all mastered chapters + silences into a continuous voice track
    concat_list = store.audio_dir / "_concat_audio.txt"
    concat_list.write_text(
        "\n".join(f"file '{p.resolve().as_posix()}'" for p in concat_segments),
        encoding="utf-8",
    )
    stitched_voice = store.audio_dir / "_narration_stitched.wav"
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
            str(stitched_voice),
        ],
        check=True,
        capture_output=True,
    )

    total_duration = probe_media_duration(stitched_voice)
    final_master = store.audio_dir / "narration_master.wav"
    ambient_rel: str | None = None

    if manifest.ambience_mode != "none":
        ambient_wav = store.audio_dir / "ambient_bed.wav"
        generate_ambient_bed(
            ambient_wav,
            duration_seconds=total_duration + 1.0,
            mode=manifest.ambience_mode,
        )
        mix_narration_and_ambience(
            narration_wav=stitched_voice,
            ambient_wav=ambient_wav,
            output_wav=final_master,
            ambience_volume_db=settings.ambience_volume_db,
        )
        ambient_rel = store.relative_str(ambient_wav)
    else:
        final_master.write_bytes(stitched_voice.read_bytes())

    return AudioTimeline(
        master_audio_file=store.relative_str(final_master),
        ambient_bed_file=ambient_rel,
        total_duration_seconds=round(probe_media_duration(final_master), 3),
        chapters=chapter_timings,
    )
