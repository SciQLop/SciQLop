"""Tests for wiring SciQLopPlots' ProductsView (the sidebar Products
browser) to components/smart_search/ -- the counterpart of
test_product_search_overlay.py's smart-search coverage, but for the sidebar
tree instead of the empty-panel popup. See docs/superpowers/specs/
2026-07-21-productsview-score-passthrough-design.md."""
import uuid
from unittest.mock import patch

import shiboken6
from PySide6.QtCore import QCoreApplication, QThreadPool
from PySide6.QtWidgets import QListView, QTextEdit

from SciQLopPlots import (
    ProductsFlatFilterModel, ProductsModel, ProductsModelNode,
    ProductsModelNodeType, ParameterType, ProductsView, ScoreMergeStrategy,
)

import SciQLop.components.products.sidebar_smart_search as mod


def _flush(qtbot):
    qtbot.wait(200)  # ProductsView's query bar debounces free_text_query_changed
    for _ in range(10):
        QCoreApplication.processEvents()


def _list_view_model(view):
    return next(
        lv.model() for lv in view.findChildren(QListView)
        if isinstance(lv.model(), ProductsFlatFilterModel))


def _visible_names(model):
    return [model.data(model.index(i, 0)) for i in range(model.rowCount())]


class TestSidebarSmartSearchWiring:
    def test_query_changed_dispatches_and_scores_surface_a_match(self, qtbot):
        token = uuid.uuid4().hex[:8]
        model = ProductsModel.instance()
        root = ProductsModelNode(f"SidebarSmartSearchRoot_{token}")
        leaf = ProductsModelNode(
            "acronym_only", "test", {"description": "totally unrelated text"},
            ProductsModelNodeType.PARAMETER, ParameterType.Scalar)
        root.add_child(leaf)
        model.add_node([], root)
        path_key = " ".join(leaf.path())

        view = ProductsView()
        qtbot.addWidget(view)
        mod.setup_sidebar_smart_search(view)

        with patch.object(mod.smart_search, "is_enabled", return_value=True), \
             patch.object(mod.smart_search, "query",
                           return_value={path_key: 100.0}) as mock_query:
            view.findChild(QTextEdit).setPlainText("magnetic field")
            _flush(qtbot)

        mock_query.assert_called_once_with("products", "magnetic field")
        assert "acronym_only" in _visible_names(_list_view_model(view))

    def test_scores_use_override_not_max(self, qtbot):
        # Regression, found live 2026-07-21: "MMS spacecraft 1 magnetic
        # field" surfaced 32 REACH cubesats (a literal-phrase match in their
        # shared metadata -- the corpus's single best NATIVE fuzzy match)
        # tied at 100% with the genuinely-relevant MMS entries (smart
        # search's own best match), and since the underlying sort isn't
        # stable, MMS was invisible in the visible slice. Default Max merge
        # normalizes each signal independently to its own max, so an
        # unrelated-but-native-best leaf and the true smart-search target
        # can both reach the ceiling. Override makes smart_search the sole
        # authority once it has an opinion: a leaf with no smart_search
        # score is excluded outright instead of competing on its native
        # score.
        token = uuid.uuid4().hex[:8]
        model = ProductsModel.instance()
        root = ProductsModelNode(f"SidebarOverrideRoot_{token}")
        native_best = ProductsModelNode(
            "native_best", "test", {"description": f"{token} magnetic field spacecraft"},
            ProductsModelNodeType.PARAMETER, ParameterType.Scalar)
        target = ProductsModelNode(
            "smart_target", "test", {"description": f"{token} totally unrelated text"},
            ProductsModelNodeType.PARAMETER, ParameterType.Scalar)
        root.add_child(native_best)
        root.add_child(target)
        model.add_node([], root)
        target_key = " ".join(target.path())

        view = ProductsView()
        qtbot.addWidget(view)
        mod.setup_sidebar_smart_search(view)

        with patch.object(mod.smart_search, "is_enabled", return_value=True), \
             patch.object(mod.smart_search, "query", return_value={target_key: 100.0}):
            view.findChild(QTextEdit).setPlainText(f"{token} magnetic field spacecraft")
            _flush(qtbot)

        names = _visible_names(_list_view_model(view))
        assert "smart_target" in names
        assert "native_best" not in names

    def test_clearing_query_reverts_merge_strategy_to_max(self, qtbot):
        # Safety net for the Override fix above: Override + a disabled
        # override_signal makes every leaf resolve to "no match" for a
        # NON-empty query, but an empty query bypasses scoring entirely
        # regardless of strategy (verified empirically) -- so this doesn't
        # blank the tree today. Still, leaving Override engaged with no
        # active smart_search score is a footgun for the next query if
        # something re-enables the signal without also fixing the
        # strategy -- revert defensively so plain Max is what a fresh query
        # starts from.
        view = ProductsView()
        qtbot.addWidget(view)
        mod.setup_sidebar_smart_search(view)

        with patch.object(mod.smart_search, "is_enabled", return_value=True), \
             patch.object(mod.smart_search, "query", return_value={}):
            bar = view.findChild(QTextEdit)
            bar.setPlainText("magnetic field")
            _flush(qtbot)
            assert view.score_merge_strategy() == ScoreMergeStrategy.Override

            bar.setPlainText("")
            _flush(qtbot)
            assert view.score_merge_strategy() == ScoreMergeStrategy.Max

    def test_not_dispatched_when_smart_search_disabled(self, qtbot):
        view = ProductsView()
        qtbot.addWidget(view)
        mod.setup_sidebar_smart_search(view)

        with patch.object(mod.smart_search, "is_enabled", return_value=False), \
             patch.object(mod.smart_search, "query") as mock_query:
            view.findChild(QTextEdit).setPlainText("magnetic field")
            _flush(qtbot)

        mock_query.assert_not_called()

    def test_clearing_query_disables_the_signal(self, qtbot):
        view = ProductsView()
        qtbot.addWidget(view)
        mod.setup_sidebar_smart_search(view)

        with patch.object(mod.smart_search, "is_enabled", return_value=True), \
             patch.object(mod.smart_search, "query", return_value={}):
            bar = view.findChild(QTextEdit)
            bar.setPlainText("magnetic field")
            _flush(qtbot)
            assert view.signal_enabled("smart_search") is True

            bar.setPlainText("")
            _flush(qtbot)
            assert view.signal_enabled("smart_search") is False

    def test_scores_not_applied_when_view_destroyed(self, qtbot):
        view = ProductsView()
        qtbot.addWidget(view)
        mod.setup_sidebar_smart_search(view)

        errors = []

        def run_inline(runnable):
            try:
                runnable.run()
            except Exception as exc:
                errors.append(exc)

        with patch.object(mod.smart_search, "is_enabled", return_value=True), \
             patch.object(mod.smart_search, "query", return_value={"a": 99.0}), \
             patch.object(shiboken6, "isValid", return_value=False), \
             patch.object(QThreadPool.globalInstance(), "start", side_effect=run_inline):
            view.findChild(QTextEdit).setPlainText("magnetic field")
            _flush(qtbot)

        assert errors == []
