from typing import Dict
from PySide6.QtGui import QIcon


icons: Dict[str, QIcon] = {}


def register_icon(name: str, icon: QIcon):
    icons[name] = icon
