from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QComboBox, QLabel,
)

from SciQLop.core.knobs import (
    KnobSpec, StringKnob, IntKnob, FloatKnob, BoolKnob, StringListKnob,
)


# Order matters: first entry is the default selection.
_TYPE_OPTIONS = (
    ("Text", "string"),
    ("Integer", "int"),
    ("Number", "float"),
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
        layout.addRow("Name:", self._name)

        self._type = QComboBox()
        for label, _ in _TYPE_OPTIONS:
            self._type.addItem(label)
        layout.addRow("Type:", self._type)

        hint = QLabel(
            "The attribute is initialized on the selected events with the "
            "type's default value. The schema is persisted with the catalog."
        )
        hint.setWordWrap(True)
        layout.addRow(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _select_type(self, label: str) -> None:
        index = self._type.findText(label)
        if index >= 0:
            self._type.setCurrentIndex(index)

    def build_spec(self) -> KnobSpec | None:
        name = self._name.text().strip()
        if not name:
            return None
        type_id = _TYPE_OPTIONS[self._type.currentIndex()][1]
        if type_id == "string":
            return StringKnob(name=name, default="")
        if type_id == "int":
            return IntKnob(name=name, default=0)
        if type_id == "float":
            return FloatKnob(name=name, default=0.0)
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
