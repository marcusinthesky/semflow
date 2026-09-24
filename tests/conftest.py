"""Shared semflow test project fixtures."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a minimal Typer/DVC project with one tracked implementation."""
    package = tmp_path / "src/example"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "stage.py").write_text(
        '''"""Stage documentation."""

from __future__ import annotations


def run(value: int) -> int:
    """Return a transformed value."""
    return value + 1


def unrelated(value: int) -> int:
    """Remain outside the tracked callback closure."""
    return value * 10
''',
        encoding="utf-8",
    )
    (package / "cli.py").write_text(
        """from __future__ import annotations

import typer

from semflow import track
from example.stage import run

app = typer.Typer()


@app.command("run")
@track
def cli_run() -> None:
    run(1)
""",
        encoding="utf-8",
    )
    (tmp_path / "dvc.yaml").write_text(
        """# Keep this comment and formatting exactly.
stages:
  example:
    cmd: example run
    deps:
    - src/example/stage.py
    - data/input.csv
    outs:
    - data/output.csv
""",
        encoding="utf-8",
    )
    (tmp_path / "semflow.toml").write_text(
        """project-root = "."
pipeline-file = "dvc.yaml"
hash-dir = ".semflow/hashes"
source-roots = ["src"]

[applications]
example = "example.cli:app"

[hashing]
ignore-docstrings = true
ignore-annotations = true
ignore-type-checking-blocks = true

[tracking]
auto-typer = true
""",
        encoding="utf-8",
    )
    for name in tuple(sys.modules):
        if name == "example" or name.startswith("example."):
            monkeypatch.delitem(sys.modules, name)
    monkeypatch.syspath_prepend(str(tmp_path / "src"))
    return tmp_path
