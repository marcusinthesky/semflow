"""CLI contract tests for check and patch."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from semflow.cli import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


def test_check_patch_preview_and_apply(project: Path) -> None:
    """The CLI is read-only by default and converges after explicit --apply."""
    config = project / "semflow.toml"
    pipeline = project / "dvc.yaml"
    before = pipeline.read_text(encoding="utf-8")

    check = runner.invoke(app, ["check", "--config", str(config)])
    assert check.exit_code == 1
    assert "patch required" in check.output

    preview = runner.invoke(app, ["patch", "--config", str(config)])
    assert preview.exit_code == 0
    assert "--- a/dvc.yaml" in preview.output
    assert pipeline.read_text(encoding="utf-8") == before

    applied = runner.invoke(app, ["patch", "--apply", "--config", str(config)])
    assert applied.exit_code == 0
    assert "applied 2 file change(s)" in applied.output

    clean = runner.invoke(app, ["check", "--config", str(config)])
    assert clean.exit_code == 0
    assert "fingerprints are current" in clean.output


def test_refresh_preview_and_apply_only_writes_json(project: Path) -> None:
    """The refresh CLI never rewrites the authored pipeline file."""
    config = project / "semflow.toml"
    pipeline = project / "dvc.yaml"
    runner.invoke(app, ["patch", "--apply", "--config", str(config)])
    instrumented = pipeline.read_text(encoding="utf-8")
    source = project / "src/example/stage.py"
    source.write_text(
        source.read_text(encoding="utf-8").replace("value + 1", "value + 2"),
        encoding="utf-8",
    )

    preview = runner.invoke(app, ["refresh", "--config", str(config)])
    assert preview.exit_code == 0
    assert "run.json" in preview.output
    assert pipeline.read_text(encoding="utf-8") == instrumented

    applied = runner.invoke(app, ["refresh", "--apply", "--config", str(config)])
    assert applied.exit_code == 0
    assert "refreshed 1 fingerprint file(s)" in applied.output
    assert runner.invoke(app, ["refresh", "--config", str(config)]).exit_code == 0
