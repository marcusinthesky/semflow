"""Semantic normalization tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from semflow.hashing import fingerprint_source, semantic_digest
from semflow.model import HashPolicy

if TYPE_CHECKING:
    from pathlib import Path

IGNORE_TYPES = HashPolicy(ignore_docstrings=True, ignore_annotations=True)


def test_format_docstrings_and_annotations_are_ignored() -> None:
    """Configured non-executable edits retain the same digest."""
    before = '''"""Old module docs."""
from __future__ import annotations

def transform(value: int) -> int:
    """Old function docs."""
    result: int = value + 1
    return result
'''
    after = '''"""New module docs."""

from __future__ import annotations

def transform(
    value: float,
) -> float:
    """New function docs."""
    result: float = value + 1
    return result
'''
    assert semantic_digest(before, IGNORE_TYPES) == semantic_digest(after, IGNORE_TYPES)


def test_runtime_change_changes_digest() -> None:
    """Executable expression changes remain invalidating."""
    before = "def transform(value: int) -> int:\n    return value + 1\n"
    after = "def transform(value: int) -> int:\n    return value + 2\n"
    assert semantic_digest(before, IGNORE_TYPES) != semantic_digest(after, IGNORE_TYPES)


def test_class_annotations_remain_semantic() -> None:
    """Retain runtime schemas even when function annotations are ignored."""
    before = "class Record:\n    value: int\n"
    after = "class Record:\n    value: str\n"
    assert semantic_digest(before, IGNORE_TYPES) != semantic_digest(after, IGNORE_TYPES)


def test_type_comments_follow_annotation_policy() -> None:
    """Retain legacy type comments unless annotation hashing is disabled."""
    before = "value = compute()  # type: int\n"
    after = "value = compute()  # type: str\n"

    assert semantic_digest(before) != semantic_digest(after)
    assert semantic_digest(before, IGNORE_TYPES) == semantic_digest(after, IGNORE_TYPES)


def test_type_checking_block_is_ignored_but_else_is_retained() -> None:
    """TYPE_CHECKING imports are noise while its runtime else branch is semantic."""
    first = """from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from example import First
else:
    VALUE = 1
"""
    second = """from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from example import Second
else:
    VALUE = 1
"""
    changed = second.replace("VALUE = 1", "VALUE = 2")
    assert semantic_digest(first, IGNORE_TYPES) == semantic_digest(second, IGNORE_TYPES)
    assert semantic_digest(first, IGNORE_TYPES) != semantic_digest(
        changed, IGNORE_TYPES
    )


def test_directory_fingerprint_is_sorted_and_detects_new_member(tmp_path: Path) -> None:
    """Cover directory member paths and semantic contents deterministically."""
    package = tmp_path / "package"
    package.mkdir()
    (package / "z.py").write_text("VALUE = 1\n", encoding="utf-8")
    (package / "a.py").write_text("VALUE = 2\n", encoding="utf-8")

    first = fingerprint_source(package, project_root=tmp_path, policy=IGNORE_TYPES)
    assert [member.path for member in first.members] == ["package/a.py", "package/z.py"]

    (package / "m.py").write_text("VALUE = 3\n", encoding="utf-8")
    second = fingerprint_source(package, project_root=tmp_path, policy=IGNORE_TYPES)
    assert first.digest != second.digest
