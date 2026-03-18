"""Shared completion and parsing helpers for all SciQLop cell/line magics."""
import shlex
from datetime import datetime, timezone


def _normalize_product_path(path: str) -> str:
    """Normalize a product path: strip root// prefix, convert // separators to /."""
    if path.startswith("root//"):
        path = path[6:]
    return path.replace("//", "/")


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
        return [_normalize_product_path(path.strip()) for path in mime.text().strip().split("\n") if path.strip()]
    return []


def _complete_panels() -> list[str]:
    """Return panel names, most recent first."""
    from SciQLop.user_api.gui import get_main_window

    mw = get_main_window()
    if mw is None:
        return []
    return list(reversed(mw.plot_panels()))


# --- Matcher API v2 completers (work across JupyterLab + QtConsole) ---

def _quote_if_needed(value: str) -> str:
    """Quote a completion value if it contains characters that would break shlex parsing."""
    if " " in value or '"' in value or "'" in value:
        return shlex.quote(value)
    return value


def _shlex_split_partial(line: str) -> list[str]:
    """shlex.split that tolerates incomplete quoting (mid-typing)."""
    try:
        return shlex.split(line)
    except ValueError:
        # Unclosed quote — close it so shlex can parse what we have
        return shlex.split(line + '"')


def _v2(func):
    """Mark a function as a Matcher API v2 completer (receives CompletionContext)."""
    func.matcher_api_version = 2
    return func


_VP_FLAGS = ["--path", "--debug", "--start", "--stop"]


def _make_result(matches, suppress=True):
    """Build a SimpleMatcherResult dict from a list of strings."""
    from IPython.core.completer import SimpleCompletion
    return {
        "completions": [SimpleCompletion(text=_quote_if_needed(m)) for m in matches],
        "suppress": suppress if matches else False,
        "ordered": True,
    }


@_v2
def _match_plot(context):
    """Matcher for %plot: product (1st arg), panel (2nd arg)."""
    line = context.line_with_cursor
    if not line.lstrip().startswith("%plot "):
        return _make_result([])
    parts = _shlex_split_partial(line)
    token = context.token
    if len(parts) <= 2:
        return _make_result(_complete_products(token))
    token_lower = token.lower()
    return _make_result([p for p in _complete_panels() if p.lower().startswith(token_lower)])


@_v2
def _match_timerange(context):
    """Matcher for %timerange: panel name on 1st arg or 4th token."""
    line = context.line_with_cursor
    if not line.lstrip().startswith("%timerange"):
        return _make_result([])
    parts = _shlex_split_partial(line)
    token = context.token
    if len(parts) <= 2 or len(parts) == 4:
        token_lower = token.lower()
        return _make_result([p for p in _complete_panels() if p.lower().startswith(token_lower)])
    return _make_result([])


@_v2
def _match_vp(context):
    """Matcher for %%vp: --path -> product, -- -> flags."""
    line = context.line_with_cursor
    if not line.lstrip().startswith("%%vp"):
        return _make_result([])
    parts = _shlex_split_partial(line)
    token = context.token
    prev = parts[-2] if len(parts) >= 2 else ""
    if prev == "--path":
        return _make_result(_complete_products(token))
    if token.startswith("-"):
        return _make_result([f for f in _VP_FLAGS if f.startswith(token)])
    return _make_result([])
