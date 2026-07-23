import uuid
from unittest.mock import patch, MagicMock
import pytest

from PySide6.QtWidgets import QLineEdit, QListView, QLabel
from SciQLopPlots import ProductsModelNodeType


class TestProductSearchOverlayCreation:
    def test_overlay_has_search_box(self, qtbot):
        from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
        overlay = ProductSearchOverlay()
        qtbot.addWidget(overlay)
        line_edit = overlay.findChild(QLineEdit)
        assert line_edit is not None
        assert "Search products" in line_edit.placeholderText()

    def test_overlay_has_result_list(self, qtbot):
        from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
        overlay = ProductSearchOverlay()
        qtbot.addWidget(overlay)
        list_view = overlay.findChild(QListView)
        assert list_view is not None
        assert not list_view.isVisible()

    def test_overlay_has_label(self, qtbot):
        from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
        overlay = ProductSearchOverlay()
        qtbot.addWidget(overlay)
        labels = overlay.findChildren(QLabel)
        texts = [l.text() for l in labels]
        assert any("Add a product" in t for t in texts)

    def test_overlay_has_drop_zone(self, qtbot):
        from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
        overlay = ProductSearchOverlay()
        qtbot.addWidget(overlay)
        labels = overlay.findChildren(QLabel)
        texts = [l.text() for l in labels]
        assert any("Drop products here" in t for t in texts)


class TestProductSearchOverlaySelection:
    def test_clicking_parameter_emits_signal(self, qtbot):
        from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
        import SciQLop.components.plotting.ui.product_search_overlay as overlay_mod

        overlay = ProductSearchOverlay()
        qtbot.addWidget(overlay)

        signals = []
        overlay.product_selected.connect(lambda p: signals.append(p))

        mock_node = MagicMock()
        mock_node.node_type.return_value = ProductsModelNodeType.PARAMETER
        overlay._result_paths = [["amda", "MMS", "MMS1", "FGM", "mms1_b_gse"]]
        mock_index = MagicMock()
        mock_index.row.return_value = 0

        with patch.object(overlay_mod, "ProductsModel") as mock_model:
            mock_model.node.return_value = mock_node
            overlay._on_result_clicked(mock_index)

        assert len(signals) == 1
        assert signals[0] == ["amda", "MMS", "MMS1", "FGM", "mms1_b_gse"]

    def test_clicking_folder_does_not_emit(self, qtbot):
        from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
        import SciQLop.components.plotting.ui.product_search_overlay as overlay_mod

        overlay = ProductSearchOverlay()
        qtbot.addWidget(overlay)

        signals = []
        overlay.product_selected.connect(lambda p: signals.append(p))

        mock_node = MagicMock()
        mock_node.node_type.return_value = ProductsModelNodeType.FOLDER
        overlay._result_paths = [["amda", "MMS"]]
        mock_index = MagicMock()
        mock_index.row.return_value = 0

        with patch.object(overlay_mod, "ProductsModel") as mock_model:
            mock_model.node.return_value = mock_node
            overlay._on_result_clicked(mock_index)

        assert len(signals) == 0

    def test_out_of_range_click_ignored(self, qtbot):
        from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
        overlay = ProductSearchOverlay()
        qtbot.addWidget(overlay)

        signals = []
        overlay.product_selected.connect(lambda p: signals.append(p))
        overlay._result_paths = []
        mock_index = MagicMock()
        mock_index.row.return_value = 5

        overlay._on_result_clicked(mock_index)
        assert len(signals) == 0


class TestTimeSyncPanelOverlay:
    def test_new_panel_has_overlay(self, qtbot):
        from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
        from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
        panel = TimeSyncPanel(name="TestPanel")
        qtbot.addWidget(panel)
        panel.show()
        assert panel._search_overlay is not None
        assert isinstance(panel._search_overlay, ProductSearchOverlay)
        assert panel._search_overlay.isVisible()

    def test_overlay_hidden_after_plot_added(self, qtbot):
        from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
        from SciQLopPlots import PlotType
        panel = TimeSyncPanel(name="TestPanel2")
        qtbot.addWidget(panel)
        assert panel._search_overlay is not None

        panel.create_plot(0, PlotType.TimeSeries)

        qtbot.waitUntil(lambda: panel._search_overlay is None, timeout=1000)
        assert panel._search_overlay is None


class TestProductSearchOverlaySmartSearch:
    def test_smart_search_scores_applied_when_enabled(self, qtbot):
        from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
        import SciQLop.components.plotting.ui.product_search_overlay as overlay_mod

        overlay = ProductSearchOverlay()
        qtbot.addWidget(overlay)
        overlay._filter_model = MagicMock()

        with patch.object(overlay_mod.smart_search, "is_enabled", return_value=True), \
             patch.object(overlay_mod.smart_search, "query", return_value={"a": 99.0}) as mock_query:
            overlay._search_box.setText("mms fgm")
            qtbot.wait(overlay._debounce.interval() + 50)
            # Wait on the *final* observable effect (set_external_scores), not on
            # mock_query.called -- Mock sets .called synchronously the instant
            # query() is invoked, before the worker thread has even reached the
            # emit_ready() line, so waiting on .called alone would race the
            # queued cross-thread signal delivery.
            qtbot.waitUntil(lambda: overlay._filter_model.set_external_scores.called, timeout=2000)

        mock_query.assert_called_once_with("products", "mms fgm")
        overlay._filter_model.set_external_scores.assert_called_once_with("smart_search", {"a": 99.0})

    def test_smart_search_not_queried_when_disabled(self, qtbot):
        from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
        import SciQLop.components.plotting.ui.product_search_overlay as overlay_mod

        overlay = ProductSearchOverlay()
        qtbot.addWidget(overlay)
        overlay._filter_model = MagicMock()

        with patch.object(overlay_mod.smart_search, "is_enabled", return_value=False), \
             patch.object(overlay_mod.smart_search, "query") as mock_query:
            overlay._search_box.setText("mms fgm")
            qtbot.wait(overlay._debounce.interval() + 50)

        mock_query.assert_not_called()
        overlay._filter_model.set_external_scores.assert_not_called()

    def test_apply_smart_search_scores_calls_real_binding_signature(self, qtbot):
        # Regression test: SciQLopPlots 0.31.0 generalized set_external_scores()
        # from a single-signal (scores) call to a named-signal (signal_name,
        # scores) call. The other tests in this class mock _filter_model, so
        # they don't exercise the real C++ binding and wouldn't catch a
        # signature mismatch (TypeError: missing signal_name).
        from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay

        overlay = ProductSearchOverlay()
        qtbot.addWidget(overlay)

        overlay._apply_smart_search_scores(0, {})

    def test_smart_search_scores_actually_surface_matches(self, qtbot):
        # Regression: SciQLopPlots 0.31.0 defaults every named external
        # signal to disabled (set_signal_enabled("smart_search", True) must
        # be called explicitly) -- set_external_scores() alone silently does
        # nothing. The other tests in this class only assert
        # set_external_scores was *called*, which doesn't catch this: the
        # call happens, it's just inert without the matching enable call.
        import uuid
        from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
        from SciQLopPlots import (
            ProductsModel, ProductsModelNode, ProductsModelNodeType,
            ParameterType, QueryParser,
        )

        token = uuid.uuid4().hex[:8]
        model = ProductsModel.instance()
        root = ProductsModelNode(f"SmartSearchEnableRoot_{token}")
        leaf = ProductsModelNode(
            "acronym_only", "test", {"description": "totally unrelated text"},
            ProductsModelNodeType.PARAMETER, ParameterType.Scalar)
        root.add_child(leaf)
        model.add_node([], root)
        path_key = " ".join(leaf.path())

        overlay = ProductSearchOverlay()
        qtbot.addWidget(overlay)
        overlay._apply_smart_search_scores(0, {path_key: 100.0})
        overlay._filter_model.set_query(QueryParser.parse("magnetic field"))
        from PySide6.QtCore import QCoreApplication
        for _ in range(10):
            QCoreApplication.processEvents()

        names = [overlay._filter_model.data(overlay._filter_model.index(i, 0))
                 for i in range(overlay._filter_model.rowCount())]
        assert "acronym_only" in names

    def test_smart_search_scores_use_override_not_max(self, qtbot):
        # Regression: default Max merge normalizes each signal independently
        # to its OWN max in the current result set, so a leaf that's the
        # single best NATIVE fuzzy match (e.g. literally contains the query
        # words) ties at the same merged score (100) as smart_search's own
        # best match, even when they're unrelated -- and since the C++ sort
        # isn't stable, the genuinely-relevant smart_search match can be
        # buried behind the coincidental native match. Verified live
        # (2026-07-21): "MMS spacecraft 1 magnetic field" surfaced 32 REACH
        # cubesats (literal-phrase-match in shared metadata) tied with 4 MMS
        # entries at 100%, MMS invisible in the visible slice. Override
        # (smart_search as the sole authority once it has an opinion) fixes
        # this: a leaf with NO smart_search score is excluded outright
        # instead of competing via its native score.
        import SciQLop.components.plotting.ui.product_search_overlay as overlay_mod
        from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
        from SciQLopPlots import (
            ProductsModel, ProductsModelNode, ProductsModelNodeType,
            ParameterType, QueryParser,
        )

        token = uuid.uuid4().hex[:8]
        model = ProductsModel.instance()
        root = ProductsModelNode(f"OverrideRoot_{token}")
        # The corpus's single best NATIVE fuzzy match for this query -- gets
        # no smart_search score at all.
        native_best = ProductsModelNode(
            "native_best", "test", {"description": f"{token} magnetic field spacecraft"},
            ProductsModelNodeType.PARAMETER, ParameterType.Scalar)
        # smart_search's target -- unrelated native text, but a decisive
        # external score.
        target = ProductsModelNode(
            "smart_target", "test", {"description": f"{token} totally unrelated text"},
            ProductsModelNodeType.PARAMETER, ParameterType.Scalar)
        root.add_child(native_best)
        root.add_child(target)
        model.add_node([], root)
        target_key = " ".join(target.path())

        overlay = ProductSearchOverlay()
        qtbot.addWidget(overlay)
        overlay._apply_smart_search_scores(0, {target_key: 100.0})
        overlay._filter_model.set_query(QueryParser.parse(f"{token} magnetic field spacecraft"))
        from PySide6.QtCore import QCoreApplication
        for _ in range(10):
            QCoreApplication.processEvents()

        names = [overlay._filter_model.data(overlay._filter_model.index(i, 0))
                 for i in range(overlay._filter_model.rowCount())]
        assert "smart_target" in names
        assert "native_best" not in names

    def test_smart_search_scores_not_applied_when_overlay_destroyed(self, qtbot):
        from PySide6.QtCore import QThreadPool
        from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
        import SciQLop.components.plotting.ui.product_search_overlay as overlay_mod

        overlay = ProductSearchOverlay()
        qtbot.addWidget(overlay)
        overlay._filter_model = MagicMock()

        # Run the QRunnable synchronously on this thread instead of a real
        # worker thread, so we can assert directly that its run() body never
        # lets an exception escape -- Qt's thread pool would otherwise
        # swallow it silently, which is exactly the failure mode the
        # shiboken6.isValid guard is meant to prevent from ever reaching a
        # real destroyed QObject.
        errors = []

        def run_inline(runnable):
            try:
                runnable.run()
            except Exception as exc:
                errors.append(exc)

        with patch.object(overlay_mod.smart_search, "is_enabled", return_value=True), \
             patch.object(overlay_mod.smart_search, "query", return_value={"a": 99.0}) as mock_query, \
             patch.object(overlay_mod.shiboken6, "isValid", return_value=False), \
             patch.object(QThreadPool.globalInstance(), "start", side_effect=run_inline):
            overlay._search_box.setText("mms fgm")
            qtbot.wait(overlay._debounce.interval() + 50)

        assert errors == []
        mock_query.assert_called_once_with("products", "mms fgm")
        overlay._filter_model.set_external_scores.assert_not_called()

    def test_rapid_edits_while_busy_coalesce_to_only_the_latest(self, qtbot):
        # Real bug report: editing a query quickly enough to space edits
        # further apart than the debounce (~150ms) but closer together
        # than score_query()'s own real latency (~150-210ms, measured
        # against the real corpus) let multiple concurrent dispatches
        # race, and whichever one *completed* last won regardless of
        # dispatch order -- e.g. toggling "MMS1 ion flux" <-> "MMS1 ions
        # flux". Fix: single-flight dispatch, mirroring
        # SmartSearchRegistry's own reindex-job pattern
        # (_trigger_reindex's job_id-busy-gate + dirty-flag-coalesce) --
        # at most one query actually runs at a time; anything requested
        # while busy replaces any earlier still-pending request instead of
        # spawning a second concurrent task, and only the latest pending
        # text is ever dispatched once the current one finishes. Same
        # reproducer as sidebar_smart_search.py's test of the same name
        # (both files shared the identical bug).
        from PySide6.QtCore import QThreadPool, QCoreApplication
        from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
        import SciQLop.components.plotting.ui.product_search_overlay as overlay_mod
        from SciQLopPlots import ProductsModel, ProductsModelNode, ProductsModelNodeType, ParameterType

        token = uuid.uuid4().hex[:8]
        model = ProductsModel.instance()
        root = ProductsModelNode(f"OverlayCoalesceRoot_{token}")
        mid_leaf = ProductsModelNode(
            "mid_leaf", "test", {"description": "totally unrelated text"},
            ProductsModelNodeType.PARAMETER, ParameterType.Scalar)
        final_leaf = ProductsModelNode(
            "final_leaf", "test", {"description": "totally unrelated text"},
            ProductsModelNodeType.PARAMETER, ParameterType.Scalar)
        root.add_child(mid_leaf)
        root.add_child(final_leaf)
        model.add_node([], root)
        mid_key = " ".join(mid_leaf.path())
        final_key = " ".join(final_leaf.path())

        overlay = ProductSearchOverlay()
        qtbot.addWidget(overlay)

        queued = []
        queried_texts = []
        responses = {"aa": {"a_key_unused": 1.0}, "aab": {mid_key: 100.0}, "aabc": {final_key: 100.0}}

        def fake_query(domain, text):
            queried_texts.append(text)
            return responses[text]

        with patch.object(overlay_mod.smart_search, "is_enabled", return_value=True), \
             patch.object(overlay_mod.smart_search, "query", side_effect=fake_query), \
             patch.object(QThreadPool.globalInstance(), "start", side_effect=lambda r: queued.append(r)):
            overlay._search_box.setText("aa")
            qtbot.wait(overlay._debounce.interval() + 50)
            assert len(queued) == 1  # first dispatch goes out immediately

            overlay._search_box.setText("aab")
            qtbot.wait(overlay._debounce.interval() + 50)
            overlay._search_box.setText("aabc")
            qtbot.wait(overlay._debounce.interval() + 50)
            assert len(queued) == 1  # "aab"/"aabc" coalesced into pending, no new dispatch yet

            queued[0].run()  # the in-flight "aa" query finishes
            assert len(queued) == 2  # its completion immediately dispatches the latest pending
            queued[1].run()
            for _ in range(10):
                QCoreApplication.processEvents()

        assert queried_texts == ["aa", "aabc"]  # "aab" was superseded before ever being queried
        names = [overlay._filter_model.data(overlay._filter_model.index(i, 0))
                 for i in range(overlay._filter_model.rowCount())]
        assert "final_leaf" in names
        assert "mid_leaf" not in names

    def test_clearing_query_while_in_flight_discards_the_stale_result(self, qtbot):
        # If the query is cleared (e.g. user deletes all text) while a
        # smart search request is still in flight, the eventually-arriving
        # result must not resurrect scores for a query that's no longer
        # active.
        from PySide6.QtCore import QThreadPool
        from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
        import SciQLop.components.plotting.ui.product_search_overlay as overlay_mod

        overlay = ProductSearchOverlay()
        qtbot.addWidget(overlay)
        overlay._filter_model = MagicMock()

        queued = []
        with patch.object(overlay_mod.smart_search, "is_enabled", return_value=True), \
             patch.object(overlay_mod.smart_search, "query", return_value={"a": 99.0}), \
             patch.object(QThreadPool.globalInstance(), "start", side_effect=lambda r: queued.append(r)):
            overlay._search_box.setText("magnetic field")
            qtbot.wait(overlay._debounce.interval() + 50)
            assert len(queued) == 1

            overlay._search_box.setText("")

            queued[0].run()  # the now-superseded (cleared) query finishes late

        overlay._filter_model.set_external_scores.assert_not_called()
