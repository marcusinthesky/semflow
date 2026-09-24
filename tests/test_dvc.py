"""DVC patch planning and application tests."""

from __future__ import annotations

import json
import stat
from typing import TYPE_CHECKING

import pytest

from semflow.config import load_config
from semflow.dvc import DvcPatchError, apply_patch, build_patch, build_refresh

if TYPE_CHECKING:
    from pathlib import Path

AUTHORED_MODE = 0o640


def test_patch_preserves_yaml_and_materializes_fingerprint(project: Path) -> None:
    """Change only the dependency scalar; preserve surrounding YAML bytes."""
    config = load_config(project / "semflow.toml")
    before = (project / "dvc.yaml").read_text(encoding="utf-8")

    plan = build_patch(config)

    assert not plan.clean
    assert (project / "dvc.yaml").read_text(encoding="utf-8") == before
    assert ".semflow/hashes/entrypoints/example/run.json" in plan.diff()

    apply_patch(plan)

    pipeline = (project / "dvc.yaml").read_text(encoding="utf-8")
    assert pipeline.startswith("# Keep this comment and formatting exactly.\n")
    assert "- .semflow/hashes/entrypoints/example/run.json" in pipeline
    assert "- data/input.csv" in pipeline
    fingerprint_path = project / ".semflow/hashes/entrypoints/example/run.json"
    document = json.loads(fingerprint_path.read_text(encoding="utf-8"))
    assert document["callback"] == "example.cli:cli_run"
    symbols = {member["symbol"] for member in document["members"]}
    assert "example.stage:run" in symbols
    assert "example.stage:unrelated" not in symbols
    assert build_patch(config).clean


def test_docstring_edit_needs_no_patch_after_instrumentation(project: Path) -> None:
    """A configured cosmetic edit leaves both DVC YAML and JSON unchanged."""
    config = load_config(project / "semflow.toml")
    apply_patch(build_patch(config))
    source = project / "src/example/stage.py"
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "Return a transformed value.", "Expanded documentation only."
        ),
        encoding="utf-8",
    )
    assert build_patch(config).clean


def test_import_line_movement_needs_no_patch_after_instrumentation(
    project: Path,
) -> None:
    """Do not leak import line numbers into a semantic binding identity."""
    config = load_config(project / "semflow.toml")
    apply_patch(build_patch(config))
    source = project / "src/example/cli.py"
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "from example.stage import run",
            "\n\nfrom example.stage import run",
        ),
        encoding="utf-8",
    )

    assert build_patch(config).clean


def test_runtime_edit_updates_only_fingerprint(project: Path) -> None:
    """An executable edit invalidates the JSON dependency without rewriting YAML."""
    config = load_config(project / "semflow.toml")
    apply_patch(build_patch(config))
    source = project / "src/example/stage.py"
    source.write_text(
        source.read_text(encoding="utf-8").replace("value + 1", "value + 2"),
        encoding="utf-8",
    )

    plan = build_patch(config)

    assert len(plan.changes) == 1
    assert plan.changes[0].path.name == "run.json"


def test_refresh_plan_contains_only_fingerprint_changes(project: Path) -> None:
    """The DVC control stage must never rewrite instrumentation YAML."""
    config = load_config(project / "semflow.toml")
    apply_patch(build_patch(config))
    source = project / "src/example/stage.py"
    source.write_text(
        source.read_text(encoding="utf-8").replace("value + 1", "value + 2"),
        encoding="utf-8",
    )

    plan = build_refresh(config)

    assert len(plan.changes) == 1
    assert plan.changes[0].path.name == "run.json"
    assert all(change.path != project / "dvc.yaml" for change in plan.changes)


def test_refresh_rejects_stale_instrumentation(project: Path) -> None:
    """Refresh must not hide a new or removed DVC code alias."""
    config = load_config(project / "semflow.toml")
    source = project / "src/example/stage.py"
    source.write_text(
        source.read_text(encoding="utf-8").replace("value + 1", "value + 2"),
        encoding="utf-8",
    )

    with pytest.raises(DvcPatchError, match="instrumentation is stale"):
        build_refresh(config)


def test_configured_control_stage_is_not_instrumented(project: Path) -> None:
    """A refresh producer may declare broad source deps without self-hashing."""
    config_path = project / "semflow.toml"
    apply_patch(build_patch(load_config(config_path)))
    pipeline = project / "dvc.yaml"
    pipeline.write_text(
        pipeline.read_text(encoding="utf-8")
        + """
  semflow_refresh:
    cmd: semflow refresh --apply
    deps:
    - src
    outs:
    - .semflow/hashes:
        cache: false
""",
        encoding="utf-8",
    )
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            "auto-typer = true",
            'auto-typer = true\ncontrol-stages = ["semflow_refresh"]',
        ),
        encoding="utf-8",
    )

    assert build_patch(load_config(config_path)).clean


def test_unrelated_function_edit_does_not_update_fingerprint(project: Path) -> None:
    """Ignore executable edits outside the tracked function closure."""
    config = load_config(project / "semflow.toml")
    apply_patch(build_patch(config))
    source = project / "src/example/stage.py"
    source.write_text(
        source.read_text(encoding="utf-8").replace("value * 10", "value * 20"),
        encoding="utf-8",
    )

    assert build_patch(config).clean


def test_typer_callback_annotation_remains_semantic(project: Path) -> None:
    """Retain callback annotations because Typer consumes them at runtime."""
    config = load_config(project / "semflow.toml")
    apply_patch(build_patch(config))
    source = project / "src/example/cli.py"
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "def cli_run() -> None:", "def cli_run() -> int:"
        ),
        encoding="utf-8",
    )

    plan = build_patch(config)

    assert len(plan.changes) == 1
    assert plan.changes[0].path.name == "run.json"


def test_track_marker_enables_entrypoint_when_auto_typer_is_disabled(
    project: Path,
) -> None:
    """Manual tracking remains available without automatic Typer instrumentation."""
    config_path = project / "semflow.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            "auto-typer = true", "auto-typer = false"
        ),
        encoding="utf-8",
    )

    plan = build_patch(load_config(config_path))

    assert ".semflow/hashes/entrypoints/example/run.json" in plan.diff()


def test_track_include_seeds_an_additional_symbol(project: Path) -> None:
    """Explicit marker includes join the inferred transitive closure."""
    source = project / "src/example/cli.py"
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "@track\ndef cli_run",
            '@track(include=("example.stage:unrelated",))\ndef cli_run',
        ),
        encoding="utf-8",
    )

    plan = build_patch(load_config(project / "semflow.toml"))
    fingerprint = next(change for change in plan if change.path.name == "run.json")
    assert fingerprint.after is not None
    symbols = {member["symbol"] for member in json.loads(fingerprint.after)["members"]}

    assert "example.stage:unrelated" in symbols


def test_unresolved_first_party_symbol_falls_back_to_module(project: Path) -> None:
    """Hash a whole module instead of dropping an unresolved first-party edge."""
    config = load_config(project / "semflow.toml")
    dynamic = project / "src/example/dynamic.py"
    dynamic.write_text(
        "def __getattr__(name: str) -> object:\n    return lambda value: value\n",
        encoding="utf-8",
    )
    source = project / "src/example/stage.py"
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "    return value + 1",
            "    from example.dynamic import dispatched\n\n"
            "    return dispatched(value)",
        ),
        encoding="utf-8",
    )

    plan = build_patch(config)
    fingerprint = next(change for change in plan if change.path.name == "run.json")
    assert fingerprint.after is not None
    document = json.loads(fingerprint.after)

    assert document["fallbacks"] == [
        {
            "module": "example.dynamic",
            "path": "src/example/dynamic.py",
            "reason": "imported reference dispatched could not resolve 'dispatched'",
        }
    ]


def test_attribute_on_global_tracks_global_without_module_fallback(
    project: Path,
) -> None:
    """A statically defined global owns its runtime attributes."""
    config = load_config(project / "semflow.toml")
    dynamic = project / "src/example/dynamic.py"
    dynamic.write_text(
        "from collections import namedtuple\n\n"
        'Fields = namedtuple("Fields", ["value"])\n',
        encoding="utf-8",
    )
    source = project / "src/example/stage.py"
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "    return value + 1",
            "    from example.dynamic import Fields\n\n"
            "    return value + len(Fields._fields)",
        ),
        encoding="utf-8",
    )

    plan = build_patch(config)
    fingerprint = next(change for change in plan if change.path.name == "run.json")
    assert fingerprint.after is not None
    document = json.loads(fingerprint.after)

    assert document["fallbacks"] == []
    assert any(
        member["symbol"] == "example.dynamic:Fields" for member in document["members"]
    )


def test_conditional_import_alias_tracks_every_static_target(project: Path) -> None:
    """Do not discard one branch when local imports reuse an alias."""
    config = load_config(project / "semflow.toml")
    package = project / "src/example"
    (package / "first.py").write_text(
        "def choose(value: int) -> int:\n    return value + 1\n",
        encoding="utf-8",
    )
    (package / "second.py").write_text(
        "def choose(value: int) -> int:\n    return value + 2\n",
        encoding="utf-8",
    )
    source = package / "stage.py"
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "    return value + 1",
            "    if value > 0:\n"
            "        from example.first import choose\n"
            "    else:\n"
            "        from example.second import choose\n\n"
            "    return choose(value)",
        ),
        encoding="utf-8",
    )

    plan = build_patch(config)
    fingerprint = next(change for change in plan if change.path.name == "run.json")
    assert fingerprint.after is not None
    symbols = {member["symbol"] for member in json.loads(fingerprint.after)["members"]}

    assert "example.first:choose" in symbols
    assert "example.second:choose" in symbols


def test_unreachable_raw_dependency_is_removed(project: Path) -> None:
    """Collapse an unrelated authored source dep into the entrypoint fingerprint."""
    config = load_config(project / "semflow.toml")
    apply_patch(build_patch(config))
    helper = project / "src/example/helper.py"
    helper.write_text("VALUE = 1\n", encoding="utf-8")
    pipeline = project / "dvc.yaml"
    pipeline.write_text(
        pipeline.read_text(encoding="utf-8").replace(
            "    - data/input.csv",
            "    # This comment documents the superseded helper dependency.\n"
            "    - src/example/helper.py\n"
            "    - data/input.csv",
        ),
        encoding="utf-8",
    )

    plan = build_patch(config)

    assert "-    - src/example/helper.py" in plan.diff()
    assert "-    # This comment documents the superseded helper dependency." in (
        plan.diff()
    )
    assert "helper.py.json" not in plan.diff()


@pytest.mark.parametrize("quote", ['"', "'"])
def test_quoted_dependency_retains_scalar_style(project: Path, quote: str) -> None:
    """Preserve authored single- or double-quote style around a dependency."""
    config = load_config(project / "semflow.toml")
    pipeline = project / "dvc.yaml"
    pipeline.write_text(
        pipeline.read_text(encoding="utf-8").replace(
            "- src/example/stage.py",
            f"- {quote}src/example/stage.py{quote}",
        ),
        encoding="utf-8",
    )

    apply_patch(build_patch(config))

    expected = f"- {quote}.semflow/hashes/entrypoints/example/run.json{quote}"
    assert expected in pipeline.read_text(encoding="utf-8")


def test_orphan_fingerprint_is_removed(project: Path) -> None:
    """Hash files no longer referenced by DVC are deleted by the patch plan."""
    config = load_config(project / "semflow.toml")
    apply_patch(build_patch(config))
    orphan = config.hash_dir / "orphan.py.json"
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_text("{}\n", encoding="utf-8")

    plan = build_patch(config)

    assert any(change.path == orphan and change.after is None for change in plan)
    apply_patch(plan)
    assert not orphan.exists()


def test_noncanonical_fingerprint_reference_is_repaired(project: Path) -> None:
    """Keep the JSON source field and DVC reference on one canonical path."""
    config = load_config(project / "semflow.toml")
    apply_patch(build_patch(config))
    canonical = config.hash_dir / "entrypoints/example/run.json"
    alternate = config.hash_dir / "entrypoints/example/renamed.json"
    canonical.rename(alternate)
    pipeline = project / "dvc.yaml"
    pipeline.write_text(
        pipeline.read_text(encoding="utf-8").replace(
            ".semflow/hashes/entrypoints/example/run.json",
            ".semflow/hashes/entrypoints/example/renamed.json",
        ),
        encoding="utf-8",
    )

    plan = build_patch(config)

    assert any(change.path == canonical and change.after is not None for change in plan)
    assert any(change.path == alternate and change.after is None for change in plan)
    apply_patch(plan)
    assert build_patch(config).clean


def test_apply_rejects_changes_made_after_planning(project: Path) -> None:
    """Do not overwrite authored YAML changed after a patch was reviewed."""
    config = load_config(project / "semflow.toml")
    plan = build_patch(config)
    pipeline = project / "dvc.yaml"
    pipeline.write_text(
        f"{pipeline.read_text(encoding='utf-8')}# concurrent edit\n",
        encoding="utf-8",
    )

    with pytest.raises(DvcPatchError, match="changed after planning"):
        apply_patch(plan)

    assert not config.hash_dir.exists()


def test_apply_preserves_authored_file_mode(project: Path) -> None:
    """Atomic replacement retains permissions on an existing DVC YAML file."""
    config = load_config(project / "semflow.toml")
    pipeline = project / "dvc.yaml"
    pipeline.chmod(AUTHORED_MODE)

    apply_patch(build_patch(config))

    assert stat.S_IMODE(pipeline.stat().st_mode) == AUTHORED_MODE
