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
