from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("SciQLop")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__author__ = 'Alexis Jeandet'
__author_email__ = 'alexis.jeandet@member.fsf.org'
__url__ = 'https://github.com/SciQLop/SciQLop'
__description__ = 'SciQLop is a scientific data analysis and visualization platform'
__license__ = 'GPL-3.0'
__keywords__ = 'scientific data analysis visualization'

import os

sciqlop_root = os.path.dirname(os.path.abspath(__file__))
