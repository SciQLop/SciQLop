"""Shared completion and parsing helpers for all SciQLop cell/line magics."""
from datetime import datetime, timezone


def _parse_time(value: str) -> float:
    """Parse a time argument as either a float timestamp or an ISO 8601 string.

    Naive ISO strings are assumed UTC. Tz-aware strings are converted to UTC.
    """
    try:
        return float(value)
    except ValueError:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).timestamp()


def _complete_products(prefix: str, max_results: int = 20) -> list[str]:
    """Fuzzy-match product paths using ProductsFlatFilterModel."""
    from SciQLopPlots import ProductsModel, ProductsFlatFilterModel, QueryParser
    from PySide6.QtWidgets import QApplication

    flat = ProductsFlatFilterModel(ProductsModel.instance())
    flat.set_query(QueryParser.parse(prefix))

    app = QApplication.instance()
    if app:
        for _ in range(100):
            app.processEvents()
            if flat.rowCount() >= max_results:
                break

    count = min(flat.rowCount(), max_results)
    if count == 0:
        return []
    indexes = [flat.index(i, 0) for i in range(count)]
    mime = flat.mimeData(indexes)
    if mime and mime.text():
        return [path.strip() for path in mime.text().strip().split("\n") if path.strip()]
    return []


def _complete_panels() -> list[str]:
    """Return panel names, most recent first."""
    from SciQLop.user_api.gui import get_main_window

    mw = get_main_window()
    if mw is None:
        return []
    return list(reversed(mw.plot_panels()))


_VP_FLAGS = ["--path", "--debug", "--start", "--stop"]


def complete_vp(completer, event):
    """Tab completer for %%vp: --path → product, -- → flags."""
    parts = event.line.split()
    prev = parts[-2] if len(parts) >= 2 else ""
    if prev == "--path":
        return _complete_products(event.symbol)
    if event.symbol.startswith("-"):
        return [f for f in _VP_FLAGS if f.startswith(event.symbol)]
    return []
