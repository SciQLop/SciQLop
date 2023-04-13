from PySide6.QtCore import QSize
from qtconsole.inprocess import QtInProcessKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget


class IPythonWidget(RichJupyterWidget):
    """Live IPython console widget.

    .. image:: img/IPythonWidget.png

    :param custom_banner: Custom welcome message to be printed at the top of
       the console.
    """

    def __init__(self, parent=None, custom_banner=None, *args, **kwargs):
        if parent is not None:
            kwargs["parent"] = parent
        super(IPythonWidget, self).__init__()
        if custom_banner is not None:
            self.banner = custom_banner
        self.setWindowTitle(self.banner)
        self.kernel_manager = kernel_manager = QtInProcessKernelManager()
        kernel_manager.start_kernel()
        self.kernel_client = kernel_client = self._kernel_manager.client()
        kernel_client.start_channels()

        def stop():
            kernel_client.stop_channels()
            kernel_manager.shutdown_kernel()

        self.exit_requested.connect(stop)
        self.setMinimumHeight(100)

    def sizeHint(self):
        """Return a reasonable default size for usage in :class:`PlotWindow`"""
        return QSize(500, 200)

    def pushVariables(self, variable_dict):
        """ Given a dictionary containing name / value pairs, push those
        variables to the IPython console widget.

        :param variable_dict: Dictionary of variables to be pushed to the
            console's interactive namespace (```{variable_name: object, …}```)
        """
        self.kernel_manager.kernel.shell.push(variable_dict)


class Console(IPythonWidget):
    """Dock Widget including a :class:`IPythonWidget` inside
    a vertical layout.

    .. image:: img/IPythonDockWidget.png

    :param available_vars: Dictionary of variables to be pushed to the
        console's interactive namespace: ``{"variable_name": object, …}``
    :param custom_banner: Custom welcome message to be printed at the top of
        the console
    :param title: Dock widget title
    :param parent: Parent :class:`qt.QMainWindow` containing this
        :class:`qt.QDockWidget`
    """

    def __init__(self, parent=None, available_vars=None, custom_banner=None,
                 title="Console"):
        super(Console, self).__init__(parent, custom_banner=custom_banner)

        self.layout().setContentsMargins(0, 0, 0, 0)

        if available_vars is not None:
            self.pushVariables(available_vars)
