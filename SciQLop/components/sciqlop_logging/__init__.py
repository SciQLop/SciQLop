import logging
import os

# The Qt logger routes lines to the in-app log dock. Without Qt — a thin
# `pip install sciqlop`, where the launcher runs but the GUI stack is only
# installed into the workspace venv — fall back to stdlib logging.
# Only the PySide6 import is guarded, so a genuine error inside logger.py
# still propagates. See tests/test_launcher_thin_imports.py.
try:
    import PySide6  # noqa: F401
    _HAS_QT = True
except ImportError:
    _HAS_QT = False

if _HAS_QT:
    from .logger import SciQLopLogger, listen_sciqlop_logger, set_log_level, getLogger, is_debug_mode
else:
    from .fallback import SciQLopLogger, listen_sciqlop_logger, set_log_level, getLogger, is_debug_mode


INFO = logging.INFO
WARNING = logging.WARNING
DEBUG = logging.DEBUG
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL



def setup(log_filename=None, log_level=None, capture_stdout=True):
    if log_level is not None:
        set_log_level(getLogger(), log_level)
