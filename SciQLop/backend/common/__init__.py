import os
from typing import Optional, AnyStr
from contextlib import closing
import socket

import asyncio
from qasync import QThreadExecutor
import functools

from PySide6.QtGui import QColor


def insort(a, x, lo=0, hi=None, key=None):
    """Insert item x in list a, and keep it sorted assuming a is sorted.

    If x is already in a, insert it to the right of the rightmost x.

    Optional args lo (default 0) and hi (default len(a)) bound the
    slice of a to be searched.

    Optional arg key is a key-function to be passed to list.sort().

    """
    if key is None:
        key = lambda x: x
    if lo < 0:
        raise ValueError('lo must be non-negative')
    if hi is None:
        hi = len(a)
    while lo < hi:
        mid = (lo + hi) // 2
        if key(x) < key(a[mid]):
            hi = mid
        else:
            lo = mid + 1
    a.insert(lo, x)


def find_available_port(start_port: int = 8000, end_port: int = 9000) -> Optional[int]:
    for port in range(start_port, end_port):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            res = sock.connect_ex(('localhost', port))
            if res != 0:
                return port
    return None


def ensure_dir_exists(path: AnyStr):
    if not os.path.exists(path):
        os.makedirs(path)


async def background_run(function, *args, **kwargs):
    loop = asyncio.get_running_loop()
    with QThreadExecutor(1) as ex:
        r = await loop.run_in_executor(ex, functools.partial(function, **kwargs), *args)
    return r


class Maybe:
    class Nothing:

        def __call__(self, *args, **kwargs):
            return self

        def __getattr__(self, item):
            return self

        def __getitem__(self, item):
            return self

        def __contains__(self, item):
            return False

        def __bool__(self):
            return False

        def __eq__(self, other):
            return type(other) is Maybe.Nothing

        def __repr__(self):
            return "Nothing"

    def __init__(self, value):
        if value is None:
            self._value = Maybe.Nothing()
        else:
            self._value = value

    def __getattr__(self, item):
        if self._value == Maybe.Nothing():
            return Maybe.Nothing()
        return getattr(self._value, item)

    def __bool__(self):
        return bool(self._value)

    def __repr__(self):
        return f"Maybe({self._value})"


def combine_colors(color1: QColor, color2: QColor) -> QColor:
    r = (color1.red() + color2.red()) // 2
    g = (color1.green() + color2.green()) // 2
    b = (color1.blue() + color2.blue()) // 2
    a = (color1.alpha() + color2.alpha()) // 2
    return QColor(r, g, b, a)
