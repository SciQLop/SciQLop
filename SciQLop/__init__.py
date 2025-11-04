__version__ = '0.10.0'
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
    return ['SciQLopPlots==0.18.0', 'speasy>=1.6.1', 'qtconsole', "humanize", 'platformdirs',
            'seaborn', "scipy", "pyside6==6.9.2", "shiboken6==6.9.2", "PySide6-QtAds==4.4.1", "IPython",
            "ipykernel<7.0.0", "jupyterlab>=4,!=4.1.0", "notebook", "ipympl", "qasync", "jinja2", "pyzstd", "PyGitHub",
            'numpy', 'expression', "pydantic"]
