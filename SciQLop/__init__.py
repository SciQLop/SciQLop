__version__ = '0.10.4'
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
    return ['SciQLopPlots==0.17.1',
            'PySide6-QtAds==4.4.0.3',
            'PySide6==6.9.2',
            'shiboken6==6.9.2',
            'speasy>=1.5.2',
            'qtconsole',
            'tscat_gui==0.6.*',
            'tscat==0.4.*',
            'humanize',
            'platformdirs',
            'seaborn',
            'scipy',
            'ipython==8.37.0',
            'ipykernel==6.29.5',
            'ipympl==0.9.7',
            'ipywidgets==8.1.7',
            'jupyter-events==0.12.0',
            'jupyter-lsp==2.2.5',
            'jupyter_client==8.6.3',
            'jupyter_core==5.8.1',
            'jupyter_server==2.16.0',
            'jupyter_server_terminals==0.5.3',
            'jupyterlab==4.4.4',
            'jupyterlab_pygments==0.3.0',
            'jupyterlab_server==2.27.3',
            'jupyterlab_widgets==3.0.15',
            'matplotlib==3.10.3',
            'matplotlib-inline==0.1.7',
            'notebook==7.4.4',
            'notebook_shim==0.2.4',
            'tornado==6.5.1',
            'pyzmq==27.0.0',
            'qasync',
            'jinja2',
            'pyzstd',
            'PyGitHub',
            'numpy',
            'expression',
            'httpx_ws>=0.7.1,<0.8.0',
            'pycrdt-websocket>=0.15.4,<0.16.0',
            'pycrdt']
