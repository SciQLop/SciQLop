from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QApplication, QFormLayout, QTextBrowser, QLabel, QPushButton
from ..backend.IPythonKernel import InternalIPKernel
from ..backend.jupyter_clients.clients_manager import ClientsManager as IPythonKernelClientsManager
from ..backend.icons import register_icon, icons
from ..backend.sciqlop_application import sciqlop_app

register_icon("Jupyter", QIcon("://icons/Jupyter_logo.svg"))
register_icon("JupyterConsole", QIcon("://icons/JupyterConsole.svg"))


class KernelInfoWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setLayout(QFormLayout())
        self._kernel_info = QLabel("Kernel info")
        self._kernel_info.setWordWrap(True)
        self._kernel_info.setMinimumSize(QSize(0, 0))
        self.layout().addWidget(self._kernel_info)
        self._kernel_info.setText("Kernel info")


class IPythonKernelManager(QWidget):
    """A custom Qt widget for IPykernel."""
    jupyterlab_started = Signal(str)

    def __init__(self, app: QApplication, parent=None, available_vars=None, ):
        """Initialize the widget."""
        QWidget.__init__(self, parent)
        self.setWindowTitle("IPython Kernel Manager")
        self.ipykernel = InternalIPKernel()
        self.app = app
        self.ipykernel.init_ipkernel('qt')
        self.ipykernel_clients_manager = IPythonKernelClientsManager(self.ipykernel.connection_file)
        self.ipykernel_clients_manager.jupyterlab_started.connect(self.jupyterlab_started)
        self.setup_ui()
        self.app.aboutToQuit.connect(self.ipykernel_clients_manager.cleanup)
        if available_vars is not None:
            self.ipykernel.push_variables(available_vars)


    def pushVariables(self, variable_dict):
        self.ipykernel.push_variables(variable_dict)

    def quit(self):
        self.ipykernel_clients_manager.cleanup()
        self.ipykernel.ipykernel.shell.run_cell("quit()")

    def setup_ui(self):
        self.setLayout(QFormLayout())
        self.layout().addWidget(KernelInfoWidget(self))
        new_qt_console = QPushButton("New QtConsole")
        new_qt_console.setIcon(icons.get("JupyterConsole"))
        new_qt_console.clicked.connect(self.ipykernel_clients_manager.new_qt_console)
        start_jupyterlab = QPushButton("Start JupyterLab")
        start_jupyterlab.setIcon(icons.get("Jupyter"))
        start_jupyterlab.clicked.connect(self.ipykernel_clients_manager.start_jupyterlab)
        self.layout().addWidget(new_qt_console)
        self.layout().addWidget(start_jupyterlab)

    def start(self):
        self.ipykernel.start()
