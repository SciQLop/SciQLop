def test_hint_shown_once(tmp_path, monkeypatch, qapp):
    from SciQLop.components.settings.backend import entry as entry_mod
    monkeypatch.setattr(entry_mod, "SCIQLOP_CONFIG_DIR", str(tmp_path))
    shown = []
    import SciQLop.components.plotting.ui.time_sync_panel as tsp
    monkeypatch.setattr(tsp, "_show_knob_hint", lambda parent: shown.append(True))
    tsp._maybe_show_knob_hint(None)
    tsp._maybe_show_knob_hint(None)
    assert shown == [True]


def test_hint_respects_dismissal(tmp_path, monkeypatch, qapp):
    from SciQLop.components.settings.backend import entry as entry_mod
    monkeypatch.setattr(entry_mod, "SCIQLOP_CONFIG_DIR", str(tmp_path))
    from SciQLop.components.plotting.backend.knob_hint_settings import KnobHintSettings
    with KnobHintSettings() as s:
        s.parameterized_drop_hint_dismissed = True
    shown = []
    import SciQLop.components.plotting.ui.time_sync_panel as tsp
    monkeypatch.setattr(tsp, "_show_knob_hint", lambda parent: shown.append(True))
    tsp._maybe_show_knob_hint(None)
    assert shown == []
