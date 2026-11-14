"""The questions the plugin asks: which file and format, which band for TFCat, which item of a list,
and whether to move local catalogues to the account."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox

from .transfer import FILE_FILTERS, Format, format_for_filter


def ask_export_path(name: str) -> tuple[Format, Path] | None:
    path, chosen = QFileDialog.getSaveFileName(QApplication.activeWindow(), "Export catalogue", name, FILE_FILTERS)
    fmt = format_for_filter(chosen)
    if not path or fmt is None:
        return None
    path = Path(path)
    return fmt, path if path.suffix else path.with_suffix(fmt.suffix)


def ask_import_path() -> tuple[Format, Path] | None:
    path, chosen = QFileDialog.getOpenFileName(QApplication.activeWindow(), "Import catalogues", "", FILE_FILTERS)
    fmt = format_for_filter(chosen)
    return (fmt, Path(path)) if path and fmt is not None else None


def parse_value_range(text: str) -> tuple[float, float] | None:
    try:
        low, high = (float(part) for part in text.replace(";", ",").split(","))
    except ValueError:
        return None
    return (low, high) if low < high else None


def ask_value_range(axis: tuple[str, str] | None) -> tuple[float, float] | None:
    quantity, unit = axis or ("frequency", "Hz")
    text, ok = QInputDialog.getText(
        QApplication.activeWindow(), "TFCat band",
        f"TFCat draws each event as an area. Some events have no shape:\n"
        f"give the {quantity} band to draw them over, as 'low, high' in {unit}:")
    return parse_value_range(text) if ok else None


def ask_choice(title: str, label: str, items: list[str]) -> int | None:
    """The index of the chosen item."""
    if not items:
        return None
    item, ok = QInputDialog.getItem(QApplication.activeWindow(), title, label, items, 0, False)
    return items.index(item) if ok else None


def ask_move(names: list[str], target: str) -> bool:
    """Asked once, at the first sign-in that finds catalogues kept on this computer."""
    box = QMessageBox(QMessageBox.Icon.Question, "Move your catalogues to your account?",
                      f"Catalogues are kept on this computer ({', '.join(names)}).\n\n"
                      f"Move them into '{target}', your own project on the server? They are then "
                      f"saved with your account and follow you to other computers. Nobody else sees them.\n\n"
                      f"Not now keeps them here; right-click them > Move into '{target}' later.",
                      QMessageBox.StandardButton.NoButton, QApplication.activeWindow())
    move = box.addButton("Move", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Not now", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    return box.clickedButton() is move
