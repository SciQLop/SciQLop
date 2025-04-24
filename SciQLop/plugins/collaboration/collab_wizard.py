from PySide6.QtWidgets import QWidget, QFormLayout, QLineEdit, QVBoxLayout
from PySide6.QtWidgets import QWizard, QWizardPage, QRadioButton
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtCore import QRegularExpression, Signal
from uuid import uuid4
from enum import IntEnum


class Pages(IntEnum):
    """
    Enum for the pages in the collaboration wizard.
    """
    CollabStart = 0
    CollabJoin = 1
    CollabCreate = 2


class Result(IntEnum):
    """
    Enum for the result of the collaboration wizard.
    """
    Nothing = 0
    Create = 1
    Join = 2


class CollabStartPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Collaboration Setup")
        self.setSubTitle("Do you want to start a new collaboration or join an existing room?")
        self._start_new = QRadioButton("Start a new collaboration session")
        self._start_new.setChecked(True)
        self._join_existing = QRadioButton("Join an existing room")
        self._join_existing.setChecked(False)
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self._start_new)
        self.layout().addWidget(self._join_existing)

    def initializePage(self, /):
        super().initializePage()
        self.setButtonText(QWizard.WizardButton.NextButton, "Next")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Cancel")

    def nextId(self, /):
        if self._start_new.isChecked():
            return Pages.CollabCreate
        elif self._join_existing.isChecked():
            return Pages.CollabJoin
        return -1


class CollabJoinPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Join an existing room")
        self.setSubTitle("Enter room URL to join.")
        layout = QFormLayout()
        self.setLayout(layout)
        self._collab_url = QLineEdit()
        self._collab_url.setToolTip("Room URL")
        # self._collab_url.setValidator(
        #    QRegularExpressionValidator(
        #        QRegularExpression("https://[\\w\\d\\-_/.]+\\.\\w+/[\\w\\d\\-_/]+/collaboration/.*",
        #                           QRegularExpression.PatternOption.CaseInsensitiveOption)))
        self.registerField("collab_url*", self._collab_url)
        layout.addRow("Room URL:", self._collab_url)
        self._collab_url.setPlaceholderText("e.g. https://sciqlop.lpp.polytechnique.fr/collab/my_room")

    def initializePage(self, /):
        super().initializePage()
        self.setButtonText(QWizard.WizardButton.NextButton, "Connect")

    def validatePage(self):
        collab_url = self.field("collab_url")
        if not collab_url:
            return False
        if not collab_url.startswith("https://") or not collab_url.startswith("http://"):
            return False
        return True

    def nextId(self, /):
        return -1


class CollabCreatePage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Create Collaboration Session")
        self.setSubTitle("Enter the server URL and room ID to create a new collaboration session.")
        layout = QFormLayout()
        self.setLayout(layout)
        self._server_url = QLineEdit("")
        self.registerField("server_url*", self._server_url)
        layout.addRow("Server URL:", self._server_url)
        self._room_id = QLineEdit()
        self.registerField("room_id*", self._room_id)
        self._room_id.setToolTip("Collaboration room ID")
        layout.addRow("Room ID:", self._room_id)
        self._room_id.setPlaceholderText("e.g. MySciQLopRoom123")

    def initializePage(self, /):
        super().initializePage()
        self.setButtonText(QWizard.WizardButton.NextButton, "Create")
        self._server_url.setText("https://sciqlop.lpp.polytechnique.fr/collab")
        self._room_id.setText(uuid4().hex)

    def validatePage(self):
        server_url = self.field("server_url")
        room_id = self.field("room_id")
        if not server_url or not room_id:
            return False
        return True

    def nextId(self, /):
        return -1


class CollabWizard(QWizard):
    done = Signal(int, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Collaboration Setup")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)
        self.setOption(QWizard.WizardOption.IndependentPages, True)
        self.setPage(Pages.CollabStart, CollabStartPage())
        self.setPage(Pages.CollabJoin, CollabJoinPage())
        self.setPage(Pages.CollabCreate, CollabCreatePage())
        self.setStartId(Pages.CollabStart)
        self._last_result = Result.Nothing
        self.button(QWizard.WizardButton.FinishButton).clicked.connect(self._on_finish)
        self._server_url = ""
        self._room_id = ""

    def _on_finish(self):
        if self.currentId() == Pages.CollabJoin:
            self._last_result = Result.Join
            split = self.field("collab_url").split("/")
            self._server_url = "/".join(split[:-1])  # Remove /room_id
            self._room_id = split[-1]
            self.done.emit(self._last_result, self._server_url, self._room_id)
        elif self.currentId() == Pages.CollabCreate:
            self._last_result = Result.Create
            self._server_url = self.field("server_url")
            self._room_id = self.field("room_id")
            self.done.emit(self._last_result, self._server_url, self._room_id)

    @property
    def last_result(self):
        return self._last_result

    @property
    def server_url(self):
        return self._server_url

    @property
    def room_id(self):
        return self._room_id

    def restart(self, /):
        self._last_result = Result.Nothing
        super().restart()
