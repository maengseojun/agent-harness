"""Tests for the explore-controller rules in self_check.py (MAE-272).

Run: python3 -m pytest -q scripts/test_self_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import self_check  # noqa: E402

ASSETS = Path(__file__).resolve().parent.parent / "assets"
EXPLORE = (ASSETS / "template-explore.html").read_text(encoding="utf-8")


def errors_for(tmp_path: Path, source: str) -> list[str]:
    path = tmp_path / "diagram.html"
    path.write_text(source, encoding="utf-8")
    return self_check.verify(path)


@pytest.mark.parametrize("name", ["template-explore.html", "template-motion.html", "template.html"])
def test_shipped_templates_pass(name: str) -> None:
    assert self_check.verify(ASSETS / name) == []


def test_edited_explore_controller_fails(tmp_path: Path) -> None:
    edited = EXPLORE.replace("geometry never implies a route", "geometry may imply a route", 1)
    assert edited != EXPLORE
    errors = errors_for(tmp_path, edited)
    assert any("exactly match the controller in template-explore.html" in e for e in errors)


def test_edge_to_missing_node_fails(tmp_path: Path) -> None:
    broken = EXPLORE.replace('data-from="receipt" data-to="ship"', 'data-from="receipt" data-to="nowhere"', 1)
    assert broken != EXPLORE
    assert any("data-to='nowhere' names no data-node" in e for e in errors_for(tmp_path, broken))


def test_duplicate_node_id_fails(tmp_path: Path) -> None:
    broken = EXPLORE.replace('data-node="linear"', 'data-node="receipt"', 1)
    assert broken != EXPLORE
    assert any("duplicate data-node ids: receipt" in e for e in errors_for(tmp_path, broken))


def test_node_id_with_whitespace_fails(tmp_path: Path) -> None:
    broken = EXPLORE.replace('data-node="receipt"', 'data-node="receipt "', 1)
    assert broken != EXPLORE
    errors = errors_for(tmp_path, broken)
    assert any("data-node id 'receipt '" in e for e in errors)
    assert any("names no data-node" in e for e in errors)


def test_step_target_missing_fails(tmp_path: Path) -> None:
    broken = EXPLORE.replace('data-target="gate"', 'data-target="ghost"', 1)
    assert broken != EXPLORE
    assert any("data-target='ghost'" in e for e in errors_for(tmp_path, broken))


def test_node_without_kind_fails(tmp_path: Path) -> None:
    broken = EXPLORE.replace('data-node="user" data-kind="external"', 'data-node="user"', 1)
    assert broken != EXPLORE
    assert any("'user' needs a data-kind" in e for e in errors_for(tmp_path, broken))


def test_missing_explore_controller_fails(tmp_path: Path) -> None:
    start = EXPLORE.index("<script data-diagram-explore>")
    end = EXPLORE.index("</script>", start) + len("</script>")
    broken = EXPLORE[:start] + EXPLORE[end:]
    assert "<script" not in broken
    assert any("needs the canonical data-diagram-explore controller" in e for e in errors_for(tmp_path, broken))


def test_unknown_script_attribute_still_fails(tmp_path: Path) -> None:
    broken = EXPLORE.replace("<script data-diagram-explore>", "<script data-diagram-other>", 1)
    assert broken != EXPLORE
    assert any("must carry only one canonical attribute" in e for e in errors_for(tmp_path, broken))


def test_explore_does_not_require_motion_root(tmp_path: Path) -> None:
    assert not any("data-motion-root" in e for e in errors_for(tmp_path, EXPLORE))
