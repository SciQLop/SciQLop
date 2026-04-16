"""Tests for the agent products_tree browser.

The products_tree module lives deep in the agents package, which pulls
in the full SciQLop app at import time.  We load only the file itself
with its package set so relative imports resolve to mocks.
"""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_PKG = "SciQLop.components.agents.tools"
_MOD_NAME = f"{_PKG}.products_tree"
_MOD_PATH = (
    Path(__file__).resolve().parents[1]
    / "SciQLop" / "components" / "agents" / "tools" / "products_tree.py"
)


@pytest.fixture()
def ptree():
    """Load products_tree.py in isolation, mocking its dependencies."""
    # Stub out the parent package and sibling module so relative imports work
    pkg_stub = MagicMock()
    text_stub = MagicMock()
    text_stub.first_line = lambda s: s.split("\n", 1)[0]

    saved = {}
    for key in (_PKG, f"{_PKG}._text", _MOD_NAME):
        saved[key] = sys.modules.get(key)

    sys.modules[_PKG] = pkg_stub
    sys.modules[f"{_PKG}._text"] = text_stub

    spec = importlib.util.spec_from_file_location(
        _MOD_NAME, _MOD_PATH,
        submodule_search_locations=[],
    )
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = _PKG
    spec.loader.exec_module(mod)

    yield mod

    # restore
    for key, val in saved.items():
        if val is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = val


class _FakeNodeTypes:
    PARAMETER = "PARAMETER"


def _make_model(node_result, row_names=None):
    """Build a mock ProductsModel.

    node_result: what pm.node([]) returns (None to simulate missing root).
    row_names:   top-level provider names exposed via QAbstractItemModel API.
    """
    pm = MagicMock()
    pm.node.return_value = node_result

    if row_names is None:
        row_names = []

    pm.rowCount.return_value = len(row_names)

    def _index(row, _col, _parent):
        idx = MagicMock()
        idx.data.return_value = row_names[row] if row < len(row_names) else None
        return idx

    pm.index.side_effect = _index
    return pm


# --- _split_path ---

def test_split_path_empty(ptree):
    assert ptree._split_path("") == []
    assert ptree._split_path("  ") == []


def test_split_path_double_slash(ptree):
    assert ptree._split_path("speasy//amda//Parameters") == [
        "speasy", "amda", "Parameters",
    ]


def test_split_path_single_slash_fallback(ptree):
    assert ptree._split_path("speasy/amda") == ["speasy", "amda"]


# --- _render_root ---

def test_render_root_truly_empty(ptree):
    """No root node AND no rows → reports empty tree."""
    pm = _make_model(node_result=None, row_names=[])
    result = ptree._render_root(pm, _FakeNodeTypes)
    assert "empty" in result.lower()


def test_render_root_no_root_node_but_has_providers(ptree):
    """Bug reproducer: pm.node([]) is None but providers exist as rows.

    Before the fix, this incorrectly reported 'no providers loaded'.
    """
    pm = _make_model(node_result=None, row_names=["speasy"])
    result = ptree._render_root(pm, _FakeNodeTypes)
    assert "speasy" in result
    assert "empty" not in result.lower()
    assert "no providers" not in result.lower()


def test_render_root_no_root_node_multiple_providers(ptree):
    pm = _make_model(node_result=None, row_names=["speasy", "local"])
    result = ptree._render_root(pm, _FakeNodeTypes)
    assert "speasy" in result
    assert "local" in result
    assert "Providers (2)" in result
