def test_hint_default_not_dismissed(tmp_path, monkeypatch):
    from SciQLop.components.settings.backend import entry as entry_mod
    monkeypatch.setattr(entry_mod, "SCIQLOP_CONFIG_DIR", str(tmp_path))
    from SciQLop.components.plotting.backend.knob_hint_settings import KnobHintSettings
    s = KnobHintSettings()
    assert s.parameterized_drop_hint_dismissed is False


def test_hint_dismissal_persists(tmp_path, monkeypatch):
    from SciQLop.components.settings.backend import entry as entry_mod
    monkeypatch.setattr(entry_mod, "SCIQLOP_CONFIG_DIR", str(tmp_path))
    from SciQLop.components.plotting.backend.knob_hint_settings import KnobHintSettings
    with KnobHintSettings() as s:
        s.parameterized_drop_hint_dismissed = True
    s2 = KnobHintSettings()
    assert s2.parameterized_drop_hint_dismissed is True
