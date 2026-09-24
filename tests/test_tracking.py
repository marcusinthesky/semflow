"""Tracking metadata and Typer callback discovery tests."""

from __future__ import annotations

import sys
from types import ModuleType
from typing import TYPE_CHECKING, Protocol, cast

import typer
from typer.core import TyperCommand

from semflow.discovery import discover_command, parse_authored_command
from semflow.tracking import TrackSpec, track, tracking_spec

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest


class _CommandInitializer(Protocol):
    def __call__(self, name: str | None, **kwargs: object) -> None: ...


def test_track_preserves_callable_identity_and_metadata() -> None:
    """A tracked callback remains the exact function object Typer receives."""

    def callback() -> None:
        pass

    tracked = track(callback)

    assert tracked is callback
    assert tracking_spec(callback) == TrackSpec()


def test_discovery_unwraps_typer_callback_and_retains_track_spec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve the original marked callable behind Typer's Click wrapper."""
    app = typer.Typer()

    @app.command("sample")
    @track(include=("example.worker:run",))
    def sample() -> None:
        pass

    @app.command("other")
    def other() -> None:
        pass

    module = ModuleType("semflow_test_app")
    module.__dict__["app"] = app
    monkeypatch.setitem(sys.modules, module.__name__, module)

    target = discover_command(
        "sample-app",
        ("sample",),
        overrides={"sample-app": "semflow_test_app:app"},
    )

    assert target.callback is sample
    assert tracking_spec(target.callback) == TrackSpec(include=("example.worker:run",))


def test_discovery_uses_registered_callback_before_custom_command_wrapper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Custom Click command classes cannot hide the authored Typer callback."""

    class WrappedCommand(TyperCommand):
        def __init__(self, name: str | None, **kwargs: object) -> None:
            callback = cast("Callable[[], object]", kwargs["callback"])

            def wrapper() -> object:
                return callback()

            kwargs["callback"] = wrapper
            initializer = cast("_CommandInitializer", super().__init__)
            initializer(name, **kwargs)

    app = typer.Typer()

    @app.command("sample", cls=WrappedCommand)
    def sample() -> None:
        pass

    module = ModuleType("semflow_wrapped_app")
    module.__dict__["app"] = app
    monkeypatch.setitem(sys.modules, module.__name__, module)

    target = discover_command(
        "wrapped-app",
        ("sample",),
        overrides={"wrapped-app": "semflow_wrapped_app:app"},
    )

    assert target.callback is sample


def test_parse_authored_command_expands_dvc_vars() -> None:
    """Find the application and command after expanding a DVC command prefix."""
    parsed = parse_authored_command(
        "${py_app} sample --value ${item.value}",
        variables={"py_app": "uv run --project src/python sample-app"},
        applications=frozenset({"sample-app"}),
    )

    assert parsed == ("sample-app", ("sample",))
