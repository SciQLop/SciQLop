from __future__ import annotations

import re

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QComboBox, QLabel,
)

from SciQLop.core.knobs import (
    KnobSpec, StringKnob, IntKnob, FloatKnob, BoolKnob, StringListKnob, DatetimeKnob,
)
from SciQLop.core.ui.tooltips import rich_tooltip
from SciQLop.core.ui import fit_combo_to_content


# Mirrors tscat's own attribute-key rule (tscat.base._valid_key, private).
# tscat silently drops an attribute whose name doesn't match this -- both the
# value write and any later read-back -- rather than raising, so a name
# rejected here would otherwise vanish without a trace on the next reload.
_VALID_ATTRIBUTE_NAME = re.compile(r"^[A-Za-z][A-Za-z_0-9]*$")

# Order matters: first entry is the default selection.
_TYPE_OPTIONS = (
    ("Text", "string"),
    ("Integer", "int"),
    ("Number", "float"),
    ("Date/Time", "datetime"),
    ("Yes/No", "bool"),
    ("Tags", "tags"),
)


class AddAttributeDialog(QDialog):
    """Form to declare a new event metadata attribute (name + type).

    The dialog produces a `KnobSpec` describing the chosen type with sensible
    defaults; min/max/choices fine-tuning is intentionally not exposed here
    (kept simple for v1).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add attribute")
        layout = QFormLayout(self)

        self._name = QLineEdit()
        self._name.setPlaceholderText("attribute_name")
        self._name.setToolTip(rich_tooltip(
            "Name",
            "The metadata key stored on each event. Letters, digits and "
            "underscores only, starting with a letter -- no spaces."))
        layout.addRow("Name:", self._name)

        self._name_error = QLabel()
        self._name_error.setWordWrap(True)
        self._name_error.setStyleSheet("color: #cc4444;")
        self._name_error.setVisible(False)
        layout.addRow("", self._name_error)

        self._type = QComboBox()
        for label, _ in _TYPE_OPTIONS:
            self._type.addItem(label)
        fit_combo_to_content(self._type)
        self._type.setToolTip(rich_tooltip(
            "Type",
            "The kind of value this attribute holds."))
        layout.addRow("Type:", self._type)

        hint = QLabel(
            "The attribute is initialized on the selected events with the "
            "type's default value. The schema is persisted with the catalog."
        )
        hint.setWordWrap(True)
        layout.addRow(hint)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addRow(self._buttons)
        self._name.textChanged.connect(self._sync_ok_button)
        self._sync_ok_button()

    def _sync_ok_button(self) -> None:
        name = self._name.text().strip()
        valid = bool(name) and bool(_VALID_ATTRIBUTE_NAME.match(name))
        ok = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setEnabled(valid)
        show_error = bool(name) and not valid
        self._name_error.setText(
            "Letters, digits and underscores only, starting with a letter." if show_error else ""
        )
        self._name_error.setVisible(show_error)

    def _select_type(self, label: str) -> None:
        index = self._type.findText(label)
        if index >= 0:
            self._type.setCurrentIndex(index)

    def build_spec(self) -> KnobSpec | None:
        name = self._name.text().strip()
        if not _VALID_ATTRIBUTE_NAME.match(name):
            return None
        type_id = _TYPE_OPTIONS[self._type.currentIndex()][1]
        if type_id == "string":
            return StringKnob(name=name, default="")
        if type_id == "int":
            return IntKnob(name=name, default=0)
        if type_id == "float":
            return FloatKnob(name=name, default=0.0)
        if type_id == "datetime":
            return DatetimeKnob(name=name, default="")
        if type_id == "bool":
            return BoolKnob(name=name, default=False)
        if type_id == "tags":
            return StringListKnob(name=name, default=())
        return None


def run_add_attribute_dialog(parent=None) -> KnobSpec | None:
    """Open the dialog modally and return the chosen `KnobSpec`, or `None` if
    cancelled or the name is empty."""
    dialog = AddAttributeDialog(parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.build_spec()
