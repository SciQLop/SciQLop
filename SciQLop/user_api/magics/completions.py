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
    """Fuzzy-match product paths using ProductsFlatFilterModel.

    Waits for all batches to finish so results are sorted by relevance score.
    """
    from SciQLopPlots import ProductsModel, ProductsFlatFilterModel, QueryParser
    from PySide6.QtWidgets import QApplication

    flat = ProductsFlatFilterModel(ProductsModel.instance())
    flat.set_query(QueryParser.parse(prefix))

    # Pump the event loop until the model finishes processing all batches.
    # The model sorts by score only after all batches complete, so breaking
    # early would return unsorted (effectively random-order) results.
    app = QApplication.instance()
    if app:
        prev_count = -1
        stable_rounds = 0
        for _ in range(500):
            app.processEvents()
            cur = flat.rowCount()
            if cur == prev_count:
                stable_rounds += 1
                if stable_rounds >= 3:
                    break
            else:
                stable_rounds = 0
                prev_count = cur

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
