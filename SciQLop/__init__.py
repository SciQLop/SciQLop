__version__ = '0.8.1'
__author__ = 'Alexis Jeandet'
__author_email__ = 'alexis.jeandet@member.fsf.org'
__url__ = 'https://github.com/SciQLop/SciQLop'
__description__ = 'SciQLop is a scientific data analysis and visualization platform'
__license__ = 'GPL-3.0'
__keywords__ = 'scientific data analysis visualization'

import os
from typing import List

sciqlop_root = os.path.dirname(os.path.abspath(__file__))


def sciqlop_dependencies() -> List[str]:
    return ['SciQLopPlots==0.14.3', 'speasy>=1.5.1', 'qtconsole', 'tscat_gui==0.4.*',
            'tscat==0.4.*', "humanize", 'platformdirs',
            'seaborn', "scipy", "pyside6==6.8.2.1", "shiboken6==6.8.2.1", "PySide6-QtAds==4.3.1.4", "IPython",
            "ipykernel", "jupyterlab>=4,!=4.1.0",
            "notebook", "ipympl", "qasync", "jinja2", "pyzstd", "PyGitHub", 'numpy>=2.0.0', 'expression',
            'httpx_ws>=0.7.1,<0.8.0', 'pycrdt-websocket>=0.15.4,<0.16.0', 'pycrdt']
