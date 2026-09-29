"""Qt's own warnings reach the session log with a time and a category (GH #139).

In #138 the key evidence was a bare `QObject::setParent: Cannot set parent,
new parent is in a different thread` line with no time on it.
"""
import os
import re
import subprocess
import sys
import textwrap


def test_configure_qt_messages_keeps_a_user_pattern(monkeypatch):
    from SciQLop.sciqlop_app import configure_qt_messages

    monkeypatch.setenv("QT_MESSAGE_PATTERN", "%{message}")
    configure_qt_messages()
    assert os.environ["QT_MESSAGE_PATTERN"] == "%{message}"


def test_qt_warnings_carry_a_time_type_and_category():
    script = textwrap.dedent("""
        from SciQLop.sciqlop_app import configure_qt_messages
        configure_qt_messages()
        from PySide6.QtCore import QCoreApplication, QLoggingCategory, qCWarning
        app = QCoreApplication([])
        qCWarning(QLoggingCategory("qt.test.category"), "something odd happened")
    """)
    env = {k: v for k, v in os.environ.items() if k != "QT_MESSAGE_PATTERN"}
    result = subprocess.run([sys.executable, "-c", script], env=env,
                            capture_output=True, text=True, timeout=60)
    line = next(l for l in result.stderr.splitlines() if "something odd happened" in l)
    assert re.match(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3} ", line), line
    assert "warning" in line
    assert "qt.test.category" in line
