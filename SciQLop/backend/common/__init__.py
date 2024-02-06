import os
from typing import Optional, AnyStr
from contextlib import closing
import socket

import asyncio
from qasync import QThreadExecutor
import functools


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
