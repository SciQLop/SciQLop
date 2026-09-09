"""catalog.create / catalog.open command-palette commands (2026-09-06 review).

Before this: both commands were literal no-op lambdas, and ProviderArg's
completions() imported a nonexistent module (catalogs.backend.catalog_provider)
and read `capabilities` as a property instead of calling it -- typing either
command in the palette raised. This is the only keyboard-first entry point
to catalogs, per the review.
"""
import pytest

from .fixtures import *


def _make_bare_main_window(qapp):
    """Construct a throwaway, plugin-free SciQLopMainWindow -- see
    pitfall-session-scoped-mainwindow-fixture-pollution: the shared session
    `main_window` fixture must not be used for state that depends on being
    freshly built. Must be called *after* any DummyProvider the test cares
    about already exists: CatalogProvider.__init__ registers with
    CatalogRegistry before its subclass sets self._catalogs, so a
    CatalogTreeModel built in between misses it (catalog-system.md's
    documented "registration timing pitfall").
    """
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    previous = getattr(qapp, "main_window", None)
    mw = SciQLopMainWindow()
    return mw, previous


@pytest.fixture
def bare_main_window(qapp, sciqlop_resources):
    mw, previous = _make_bare_main_window(qapp)
    yield mw
    mw.close()
    qapp.main_window = previous


def test_provider_arg_completions_lists_creatable_providers(qapp):
    from SciQLop.components.command_palette.arg_types import ProviderArg
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    DummyProvider(num_catalogs=0, events_per_catalog=0, name="CreatableProv")
    arg = ProviderArg()
    values = [c.value for c in arg.completions({})]
    assert "CreatableProv" in values


def test_provider_arg_completions_excludes_read_only_providers(qapp):
    from SciQLop.components.command_palette.arg_types import ProviderArg
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    class _ReadOnly(DummyProvider):
        def capabilities(self, catalog=None):
            return set()

    _ReadOnly(num_catalogs=0, events_per_catalog=0, name="ReadOnlyProv")
    arg = ProviderArg()
    values = [c.value for c in arg.completions({})]
    assert "ReadOnlyProv" not in values


def test_catalog_arg_completions_use_provider_and_uuid(qapp):
    from SciQLop.components.command_palette.arg_types import CatalogArg
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0, name="ArgProv")
    cat = provider.catalogs()[0]
    provider.mark_dirty(cat)
    arg = CatalogArg()
    completions = arg.completions({})
    values = {c.value for c in completions}
    displays = {c.display for c in completions}
    assert f"ArgProv::{cat.uuid}" in values
    # Old bug: the tree-walk picked up "New catalog…"/"New folder…"
    # placeholder rows as if they were real catalogs, and a dirty catalog's
    # DisplayRole " *" suffix leaked into the value used for lookup.
    assert not any("New catalog" in d or "New folder" in d for d in displays)
    assert not any(v.endswith(" *") for v in values)


def test_create_catalog_command_triggers_placeholder_edit(qapp, monkeypatch):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.command_palette.commands import _do_create_catalog

    provider = DummyProvider(num_catalogs=0, events_per_catalog=0, name="CmdProv")
    mw, previous = _make_bare_main_window(qapp)

    calls = []
    monkeypatch.setattr(CatalogBrowser, "_trigger_placeholder_edit",
                         lambda self, node: calls.append(node))
    try:
        _do_create_catalog(provider="CmdProv")
    finally:
        mw.close()
        qapp.main_window = previous

    assert len(calls) == 1
    assert calls[0].provider is provider


def test_create_catalog_command_unknown_provider_is_a_noop(qapp, bare_main_window):
    from SciQLop.components.command_palette.commands import _do_create_catalog
    _do_create_catalog(provider="NoSuchProvider")  # must not raise


def test_open_catalog_command_selects_the_catalog(qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.command_palette.commands import _do_open_catalog

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0, name="OpenProv")
    cat = provider.catalogs()[0]
    mw, previous = _make_bare_main_window(qapp)

    try:
        _do_open_catalog(catalog=f"OpenProv::{cat.uuid}")
        browser = mw.catalogs_browser
        assert browser._current_catalog is not None
        assert browser._current_catalog.uuid == cat.uuid
    finally:
        mw.close()
        qapp.main_window = previous


def test_open_catalog_command_unknown_value_is_a_noop(qapp, bare_main_window):
    from SciQLop.components.command_palette.commands import _do_open_catalog
    _do_open_catalog(catalog="NoSuchProvider::nope")  # must not raise
    _do_open_catalog(catalog="garbage-no-separator")  # must not raise


def test_open_catalog_command_finds_folder_nested_catalog(qapp):
    """opencode review finding #1: the lookup only scanned the provider
    node's direct children, missing every catalog with a non-empty path --
    the common case for real (tscat/cocat) providers."""
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.command_palette.commands import _do_open_catalog

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0,
                              paths=[["folder"]], name="NestedProv")
    cat = provider.catalogs()[0]
    mw, previous = _make_bare_main_window(qapp)

    try:
        _do_open_catalog(catalog=f"NestedProv::{cat.uuid}")
        browser = mw.catalogs_browser
        assert browser._current_catalog is not None
        assert browser._current_catalog.uuid == cat.uuid
    finally:
        mw.close()
        qapp.main_window = previous


def test_open_catalog_command_clears_filter_and_does_not_deselect(qapp):
    """opencode review finding #2: with an active filter hiding the target,
    mapFromSource returns an invalid index and setCurrentIndex(invalid)
    clears whatever was previously selected -- a failed open must not
    destroy the user's current selection."""
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.command_palette.commands import _do_open_catalog

    provider = DummyProvider(num_catalogs=2, events_per_catalog=0, name="FilterProv")
    first, second = provider.catalogs()
    first.name, second.name = "Alpha", "Beta"
    mw, previous = _make_bare_main_window(qapp)

    try:
        browser = mw.catalogs_browser
        browser._filter_bar.setText("Alpha")
        _do_open_catalog(catalog=f"FilterProv::{second.uuid}")
        assert browser._current_catalog is not None
        assert browser._current_catalog.uuid == second.uuid
        assert browser._filter_bar.text() == ""
    finally:
        mw.close()
        qapp.main_window = previous
