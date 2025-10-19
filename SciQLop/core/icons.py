from typing import Dict
from PySide6.QtGui import QIcon
from SciQLopPlots import Icons




def register_icon(name: str, icon: QIcon):
    Icons.add_icon(name,  icon)
