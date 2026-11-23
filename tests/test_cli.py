"""CLI smoke tests for vfactory commands."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from video_factory.cli import app

runner = CliRunner()


def test_cli_doctor_and_estimate():
    res_doc = runner.invoke(app, ["doctor"])
    assert res_doc.exit_code == 0
    assert "ffmpeg" in res_doc.stdout.lower()

    res_est = runner.invoke(app, ["estimate", "--minutes", "20", "--llm", "gemini", "--tts", "openai", "--image", "gemini"])
    assert res_est.exit_code == 0
    assert "20 min" in res_est.stdout


def test_cli_create_status_list(tmp_path: Path):
    res_create = runner.invoke(
        app,
        [
            "create",
            "How ancient lighthouses guided ships through night fog",
            "--minutes",
            "2",
            "--llm",
            "mock",
            "--tts",
            "mock",
            "--image",
            "mock",
            "--until",
            "outline",
            "--runs-dir",
            str(tmp_path),
        ],
    )
    assert res_create.exit_code == 0
    assert "Review checkpoint" in res_create.stdout

    res_list = runner.invoke(app, ["list", "--runs-dir", str(tmp_path)])
    assert res_list.exit_code == 0
    assert "1/6" in res_list.stdout
