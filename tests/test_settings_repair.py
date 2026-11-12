"""A settings file with a bad value keeps its good values, and a bad value
typed in the settings window is refused."""
from unittest.mock import patch

import pytest
import yaml
from pydantic import Field, ValidationError, model_validator

from SciQLop.components.settings.backend import entry
from SciQLop.components.settings.backend.entry import ConfigEntry


@pytest.fixture
def config_dir(tmp_path):
    with patch.object(entry, "SCIQLOP_CONFIG_DIR", str(tmp_path)):
        yield tmp_path


@pytest.fixture
def Pair(config_dir):
    class RepairPairSettings(ConfigEntry):
        category = "test"
        subcategory = "repair"
        low: float = Field(default=0.0, ge=0.0, le=100.0)
        high: float = Field(default=100.0, ge=0.0, le=100.0)
        name: str = "default"

        @model_validator(mode="after")
        def _low_below_high(self):
            if self.low >= self.high:
                raise ValueError("Low must be below high.")
            return self

    yield RepairPairSettings
    entry.SETTINGS.remove("RepairPairSettings")


def _write(cls, **values):
    with open(cls.config_file(), "w") as f:
        yaml.safe_dump(values, f)


def _saved(cls):
    with open(cls.config_file()) as f:
        return yaml.safe_load(f)


def test_one_bad_field_keeps_the_others(Pair):
    _write(Pair, low="not a number", high=80.0, name="mine")
    settings = Pair()
    assert (settings.low, settings.high, settings.name) == (0.0, 80.0, "mine")
    assert _saved(Pair) == {"low": 0.0, "high": 80.0, "name": "mine"}


def test_the_original_file_is_kept_aside(Pair):
    _write(Pair, low="not a number", high=80.0, name="mine")
    Pair()
    with open(Pair.config_file() + ".bad") as f:
        assert yaml.safe_load(f)["low"] == "not a number"


def test_the_repair_is_reported_once(Pair):
    _write(Pair, low="not a number", high=80.0, name="mine")
    Pair()
    Pair()
    notices = entry.take_repair_notices()
    assert [(n["file"], n["reset"]) for n in notices] == [(Pair.config_file(), ["low"])]
    assert entry.take_repair_notices() == []


def test_a_broken_cross_field_rule_resets_the_file(Pair):
    _write(Pair, low=60.0, high=50.0, name="mine")
    settings = Pair()
    assert (settings.low, settings.high, settings.name) == (0.0, 100.0, "default")
    assert entry.take_repair_notices()[0]["reset"] == []


def test_a_valid_file_reports_nothing(Pair):
    _write(Pair, low=10.0, high=80.0, name="mine")
    Pair()
    assert entry.take_repair_notices() == []


@pytest.mark.parametrize("value", [60.0, 200.0, "soon"])
def test_a_value_that_breaks_a_rule_is_refused(Pair, value):
    settings = Pair()
    settings.high = 50.0
    with pytest.raises(ValidationError):
        entry.validated_value(settings, "low", value)
    assert settings.low == 0.0


def test_a_good_value_comes_back_as_the_field_stores_it(Pair):
    assert entry.validated_value(Pair(), "low", "12") == 12.0


def test_checking_a_value_changes_and_announces_nothing(Pair):
    settings = Pair()
    seen = []
    Pair._notifier.changed.connect(lambda name, value: seen.append(name))
    entry.validated_value(settings, "low", 12.0)
    assert seen == [] and settings.low == 0.0


def test_a_rule_that_assigns_a_field_can_still_be_checked(config_dir):
    """The plugins settings rewrite one of their fields inside a rule."""
    from SciQLop.components.plugins.backend.settings import SciQLopPluginsSettings
    settings = SciQLopPluginsSettings()
    assert entry.validated_value(settings, "extra_plugins_folders", ["/tmp/x"]) == ["/tmp/x"]


def test_the_settings_row_shows_why_a_value_was_refused(Pair, qtbot):
    from SciQLop.components.settings.ui.setting_panel import SettingRow
    settings = Pair()
    settings.high = 50.0
    row = SettingRow("low", Pair.model_fields["low"], settings)
    qtbot.addWidget(row)
    assert row.error_label.isHidden()
    row._on_value_changed(60.0)
    assert not row.error_label.isHidden()
    assert row.error_label.text() == "Low must be below high."
    assert _saved(Pair)["low"] == 0.0
    row._on_value_changed(10.0)
    assert row.error_label.isHidden()


def test_the_real_percentile_pair_cannot_be_inverted(config_dir):
    from SciQLop.components.settings.backend.plot_backend_settings import PlotBackendSettings
    settings = PlotBackendSettings()
    with pytest.raises(ValidationError, match="below"):
        entry.validated_value(settings, "colormap_autoscale_percentile_low", 99.0)
    assert settings.colormap_autoscale_percentile_low == 2.0


# --- The repair is told to the user once, at start ---

@pytest.fixture
def parent_widget(qtbot):
    from PySide6.QtWidgets import QWidget
    widget = QWidget()
    qtbot.addWidget(widget)
    return widget


def _message_boxes(parent):
    from PySide6.QtWidgets import QMessageBox
    return parent.findChildren(QMessageBox)


def test_no_repair_shows_nothing(config_dir, parent_widget):
    from SciQLop.sciqlop_app import _notify_repaired_settings
    _notify_repaired_settings(parent_widget)
    assert _message_boxes(parent_widget) == []


def test_a_repair_is_shown_once_with_the_fields_and_the_copy(Pair, parent_widget):
    from SciQLop.sciqlop_app import _notify_repaired_settings
    _write(Pair, low="not a number", high=80.0, name="mine")
    Pair()
    _notify_repaired_settings(parent_widget)
    (box,) = _message_boxes(parent_widget)
    assert not box.isModal()
    assert "repairpairsettings.yaml: low" in box.informativeText()
    assert ".bad" in box.informativeText()
    _notify_repaired_settings(parent_widget)
    assert len(_message_boxes(parent_widget)) == 1


def test_a_whole_file_reset_says_so(Pair, parent_widget):
    from SciQLop.sciqlop_app import _notify_repaired_settings
    _write(Pair, low=60.0, high=50.0)
    Pair()
    _notify_repaired_settings(parent_widget)
    assert "repairpairsettings.yaml: all settings" in _message_boxes(parent_widget)[0].informativeText()
