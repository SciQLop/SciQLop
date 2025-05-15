import os
import sys

try:
    from pyshortcuts import make_shortcut, platform
except ImportError:
    import pip
    pip.main(["install", "--upgrade", "pyshortcuts"])
    from pyshortcuts import make_shortcut, platform


def install_sciqlop():
    import pip
    pip.main(["install", "--upgrade", "sciqlop"])


def sciqlop_install_dir():
    import SciQLop 
    return os.path.dirname(SciQLop.__file__)

def create_sciqlop_shortcut(sciqlop_path, icon_path):
    try:
        make_shortcut(sciqlop_path, name='SciQLop', terminal=True, icon=icon_path, description='SciQLop shortcut')
    except Exception as e:
        print(f"Failed to create shortcut: {e}")

try:
    import SciQLop
except ImportError:
    print("SciQLop is not installed. Installing...")
    install_sciqlop()

bindir = 'Scripts' if platform.startswith('win') else 'bin'
sciqlop = os.path.normpath(os.path.join(sys.prefix, bindir, 'sciqlop'))
icon = os.path.normpath(os.path.join(sciqlop_install_dir(), 'resources','icons', 'SciQLop.ico'))

create_sciqlop_shortcut(f"{sciqlop:s}", icon_path=icon)

