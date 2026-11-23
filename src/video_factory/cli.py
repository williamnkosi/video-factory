"""Typer + Rich CLI for the Sleepy History Video Factory."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from video_factory.config import AmbienceMode, ProviderName, Settings
from video_factory.models import STAGE_ORDER, ProviderConfig, StageName, StageStatus
from video_factory.pipeline import estimate_project_cost, regenerate_item, run_pipeline
from video_factory.storage import ProjectStore, create_project, list_projects

app = typer.Typer(
    name="vfactory",
    help="Stage-gated AI agent factory for 15–30 min sleepy history YouTube documentaries.",
    no_args_is_help=True,
)
console = Console()


def _load_store(slug: str, settings: Settings) -> ProjectStore:
    project_dir = settings.resolve_runs_dir() / slug
    store = ProjectStore(project_dir)
    if not store.manifest_path.exists():
        console.print(f"[red]Project '{slug}' not found in {settings.resolve_runs_dir()}[/red]")
        raise typer.Exit(code=1)
    return store


def _print_status_table(store: ProjectStore) -> None:
    manifest = store.load_manifest()
    est = estimate_project_cost(manifest)

    header = (
        f"[bold]{manifest.slug}[/bold]  •  {manifest.target_minutes} min target "
        f"(~{est.estimated_words} words, ~{est.estimated_images} scenes)\n"
        f"Description: {manifest.description}\n"
        f"Providers: LLM=[cyan]{manifest.providers.llm}[/cyan] | "
        f"TTS=[cyan]{manifest.providers.tts}[/cyan] | "
        f"Image=[cyan]{manifest.providers.image}[/cyan]  •  "
        f"Est. API cost: [yellow]${est.total_usd:.2f}[/yellow]\n"
        f"Workspace: {store.root}"
    )
    console.print(Panel(header, title="Video Factory Project", border_style="dim"))

    table = Table(show_header=True, header_style="bold")
    table.add_column("Stage", style="bold")
    table.add_column("Status")
    table.add_column("Notes / Error")

    colors = {
        StageStatus.PENDING: "dim",
        StageStatus.RUNNING: "yellow",
        StageStatus.COMPLETED: "green",
        StageStatus.FAILED: "red",
    }
    for stage in STAGE_ORDER:
        rec = manifest.stages[stage]
        color = colors[rec.status]
        detail = rec.error if rec.status == StageStatus.FAILED else (rec.notes or "")
        table.add_row(stage.value, f"[{color}]{rec.status.value}[/{color}]", detail)

    console.print(table)


@app.command()
def create(
    description: str = typer.Argument(..., help="Topic description for the sleepy history video."),
    minutes: int = typer.Option(20, "--minutes", "-m", min=1, max=180, help="Target runtime in minutes (MVP sweet spot: 15-30)."),
    slug: str | None = typer.Option(None, "--slug", help="Optional custom project folder slug."),
    llm: ProviderName | None = typer.Option(None, "--llm", help="LLM provider: gemini | openai | mock"),
    tts: ProviderName | None = typer.Option(None, "--tts", help="TTS provider: gemini | openai | mock"),
    image: ProviderName | None = typer.Option(None, "--image", help="Image provider: gemini | openai | mock"),
    seconds_per_scene: int | None = typer.Option(None, "--seconds-per-scene", help="Average seconds per dark painterly scene."),
    ambience: AmbienceMode | None = typer.Option(None, "--ambience", help="Background sleep bed: brown_noise | soft_rain | none"),
    sleep_dimming: bool | None = typer.Option(None, "--sleep-dimming/--no-sleep-dimming", help="Gradually darken screen in second half."),
    auto: bool = typer.Option(False, "--auto", help="Run all 6 stages end-to-end without pausing."),
    until: StageName = typer.Option(StageName.OUTLINE, "--until", help="Stage to pause after when --auto is not set."),
    runs_dir: Path | None = typer.Option(None, "--runs-dir", help="Override runs output directory."),
) -> None:
    """Create a new video project from a description and run through the initial checkpoint."""
    settings = Settings()
    if runs_dir is not None:
        settings.runs_dir = runs_dir

    providers = ProviderConfig(
        llm=llm or settings.llm_provider,
        tts=tts or settings.tts_provider,
        image=image or settings.image_provider,
    )
    store, manifest = create_project(
        settings.resolve_runs_dir(),
        description,
        slug=slug,
        target_minutes=minutes,
        words_per_minute=settings.words_per_minute,
        seconds_per_scene=seconds_per_scene or settings.seconds_per_scene,
        ambience_mode=ambience or settings.ambience_mode,
        enable_sleep_dimming=settings.enable_sleep_dimming if sleep_dimming is None else sleep_dimming,
        providers=providers,
    )

    target_stage = StageName.PACKAGE if auto else until
    console.print(f"[bold green]Created project:[/bold green] {manifest.slug} -> running until [cyan]{target_stage.value}[/cyan]")

    run_pipeline(
        store,
        settings,
        until=target_stage,
        on_event=lambda st, msg: console.print(f"  [cyan]{st.value:<8}[/cyan] {msg}"),
    )
    _print_status_table(store)

    if target_stage != StageName.PACKAGE:
        next_idx = STAGE_ORDER.index(target_stage) + 1
        next_stage = STAGE_ORDER[next_idx].value
        console.print(
            f"\n[bold]Review checkpoint:[/bold] Inspect & edit files in [cyan]{store.root}[/cyan], "
            f"then continue with:\n  [green]vfactory run {manifest.slug} --until {next_stage}[/green]  "
            f"(or [green]vfactory run {manifest.slug}[/green] to finish all remaining stages)"
        )


@app.command()
def run(
    slug: str = typer.Argument(..., help="Project slug inside runs/."),
    until: StageName = typer.Option(StageName.PACKAGE, "--until", help="Stop after this stage."),
    from_stage: StageName | None = typer.Option(None, "--from-stage", help="Start/re-run from this stage."),
    force: bool = typer.Option(False, "--force", help="Re-run stages even if already marked completed."),
    runs_dir: Path | None = typer.Option(None, "--runs-dir", help="Override runs output directory."),
) -> None:
    """Resume or advance a project through the stage-gated pipeline."""
    settings = Settings()
    if runs_dir is not None:
        settings.runs_dir = runs_dir
    store = _load_store(slug, settings)

    run_pipeline(
        store,
        settings,
        until=until,
        from_stage=from_stage,
        force=force,
        on_event=lambda st, msg: console.print(f"  [cyan]{st.value:<8}[/cyan] {msg}"),
    )
    _print_status_table(store)


@app.command()
def regenerate(
    slug: str = typer.Argument(..., help="Project slug inside runs/."),
    stage: StageName = typer.Option(..., "--stage", help="Stage to patch: script | audio | visuals"),
    item: str = typer.Option(..., "--item", help="Item ID, e.g. 'chapter_02' or 'scene_004'."),
    runs_dir: Path | None = typer.Option(None, "--runs-dir", help="Override runs output directory."),
) -> None:
    """Surgically regenerate one chapter script, one chapter audio, or one scene image."""
    settings = Settings()
    if runs_dir is not None:
        settings.runs_dir = runs_dir
    store = _load_store(slug, settings)

    regenerate_item(store, settings, stage=stage, item_id=item)
    console.print(f"[green]Regenerated {stage.value}:{item}. Downstream stages marked pending.[/green]")
    _print_status_table(store)


@app.command()
def status(
    slug: str = typer.Argument(..., help="Project slug inside runs/."),
    runs_dir: Path | None = typer.Option(None, "--runs-dir", help="Override runs output directory."),
) -> None:
    """Display stage progress, provider settings, and cost estimate for a project."""
    settings = Settings()
    if runs_dir is not None:
        settings.runs_dir = runs_dir
    store = _load_store(slug, settings)
    _print_status_table(store)


@app.command(name="list")
def list_cmd(
    runs_dir: Path | None = typer.Option(None, "--runs-dir", help="Override runs output directory."),
) -> None:
    """List all projects in the runs directory."""
    settings = Settings()
    if runs_dir is not None:
        settings.runs_dir = runs_dir
    projects = list_projects(settings.resolve_runs_dir())
    if not projects:
        console.print("[dim]No projects found yet. Run `vfactory create \"...\"` to start.[/dim]")
        return

    table = Table(title="Video Factory Runs")
    table.add_column("Slug", style="bold cyan")
    table.add_column("Minutes", justify="right")
    table.add_column("Providers")
    table.add_column("Completed Stages")
    table.add_column("Description")

    for m in projects:
        done = sum(1 for st in STAGE_ORDER if m.stages[st].status == StageStatus.COMPLETED)
        provs = f"{m.providers.llm}/{m.providers.tts}/{m.providers.image}"
        desc = m.description[:52] + ("..." if len(m.description) > 52 else "")
        table.add_row(m.slug, str(m.target_minutes), provs, f"{done}/{len(STAGE_ORDER)}", desc)

    console.print(table)


@app.command()
def estimate(
    minutes: int = typer.Option(20, "--minutes", "-m", min=1, max=180),
    llm: ProviderName = typer.Option("gemini", "--llm"),
    tts: ProviderName = typer.Option("openai", "--tts"),
    image: ProviderName = typer.Option("gemini", "--image"),
    seconds_per_scene: int = typer.Option(40, "--seconds-per-scene"),
) -> None:
    """Estimate word count, scene count, and approximate API cost before starting a run."""
    from video_factory.models import ProjectManifest

    dummy = ProjectManifest(
        project_id="est",
        slug="estimate",
        description="estimate",
        target_minutes=minutes,
        seconds_per_scene=seconds_per_scene,
        providers=ProviderConfig(llm=llm, tts=tts, image=image),
    )
    est = estimate_project_cost(dummy)
    console.print(
        Panel(
            f"Target Runtime: [bold]{est.target_minutes} min[/bold]\n"
            f"Script Budget:  ~{est.estimated_words:,} words (~{est.estimated_tts_chars:,} TTS chars)\n"
            f"Visual Scenes:  ~{est.estimated_images} dark painterly 16:9 frames\n\n"
            f"LLM ({llm}):     ~${est.llm_usd:.2f}\n"
            f"TTS ({tts}):     ~${est.tts_usd:.2f}\n"
            f"Images ({image}): ~${est.image_usd:.2f}\n"
            f"[bold yellow]Estimated Total: ~${est.total_usd:.2f}[/bold yellow]",
            title="Pre-Flight Cost Estimate",
        )
    )


@app.command()
def doctor() -> None:
    """Verify local dependencies (FFmpeg/ffprobe) and configured provider keys."""
    import shutil

    settings = Settings()
    table = Table(title="Video Factory Environment Check")
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    for binary in ("ffmpeg", "ffprobe"):
        path = shutil.which(binary)
        table.add_row(
            binary,
            "[green]OK[/green]" if path else "[red]MISSING[/red]",
            path or "Install ffmpeg on PATH",
        )

    table.add_row(
        "GEMINI_API_KEY",
        "[green]SET[/green]" if settings.gemini_api_key else "[yellow]NOT SET[/yellow]",
        f"LLM={settings.gemini_llm_model}, Image={settings.gemini_image_model}",
    )
    table.add_row(
        "OPENAI_API_KEY",
        "[green]SET[/green]" if settings.openai_api_key else "[yellow]NOT SET[/yellow]",
        f"LLM={settings.openai_llm_model}, TTS={settings.openai_tts_model} ({settings.openai_tts_voice})",
    )
    table.add_row(
        "Default Providers",
        "[cyan]CONFIGURED[/cyan]",
        f"llm={settings.llm_provider}, tts={settings.tts_provider}, image={settings.image_provider}",
    )
    console.print(table)


if __name__ == "__main__":
    app()

