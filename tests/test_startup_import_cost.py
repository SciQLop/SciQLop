"""What the first window does not need stays out of SciQLop's startup imports: importing seaborn costs
about a second, and only a plot panel's colours use it."""
import os
import subprocess
import sys
import textwrap


def _imported_after(statement: str) -> set[str]:
    probe = textwrap.dedent(f"""
        import sys
        {statement}
        print(" ".join(sorted(sys.modules)))
    """)
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "SPEASY_SKIP_INIT_PROVIDERS": "1"}
    done = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, timeout=120, env=env)
    assert done.returncode == 0, done.stderr[-2000:]
    return set(done.stdout.split())


def test_the_application_and_its_theme_do_not_import_seaborn():
    modules = _imported_after("import SciQLop.core.sciqlop_application")
    assert "SciQLop.components.theming.stylesheet" in modules
    assert "seaborn" not in modules


def test_the_main_window_s_modules_do_not_import_seaborn():
    modules = _imported_after("import SciQLop.core.sciqlop_application; "
                              "from SciQLop.core.sciqlop_application import sciqlop_app; sciqlop_app(); "
                              "import SciQLop.core.ui.mainwindow")
    assert "SciQLop.components.plotting.backend.palette" in modules
    assert "seaborn" not in modules
