from typing import Optional

from platformdirs import user_data_dir as _user_data_dir
import os as _os
from pathlib import Path


def user_data_dir(compartment: Optional[str] = None, create: bool = True) -> Path:
    path = Path(_os.path.join(_user_data_dir(appname="sciqlop", appauthor="LPP", ensure_exists=True), "data",
                              compartment or ""))

    if create and not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    return path
