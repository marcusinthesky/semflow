"""Example Typer entrypoint discovered by semflow."""

from pathlib import Path

import typer

from example.stage import greeting

app = typer.Typer()


@app.callback()
def main() -> None:
    """Run example pipeline commands."""


@app.command()
def greet() -> None:
    """Write a greeting from the authored name input."""
    source = Path("data/name.txt")
    destination = Path("data/greeting.txt")
    destination.write_text(
        greeting(source.read_text(encoding="utf-8").strip()) + "\n",
        encoding="utf-8",
    )
