import os
from typing import Optional, AnyStr, Protocol
from contextlib import closing
import socket

import asyncio
from qasync import QThreadExecutor
import functools

from PySide6.QtGui import QColor

from .signal_rate_limiter import SignalRateLimiter


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


class Nothing:
    def __init__(self, exception=None):
        self._exception = exception

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
        return type(other) is Nothing

    def __repr__(self):
        return "Nothing"

    def and_then(self, func, *args, **kwargs):
        return self

    @property
    def exception(self):
        return self._exception


class Something:
    def __init__(self, value):
        assert value is not None, "Something cannot be None"
        self._value = value

    def __call__(self, *args, **kwargs):
        return self._value

    def __getattr__(self, item):
        return getattr(self._value, item)

    def __getitem__(self, item):
        return self._value[item]

    def __contains__(self, item):
        return item in self._value

    def __bool__(self):
        return True

    def __eq__(self, other):
        return (type(other) is Something and self._value == other._value) or other == self._value

    def __repr__(self):
        return f"Something({self._value})"

    @property
    def value(self):
        return self._value

    def and_then(self, func, *args, **kwargs):
        try:
            return Maybe(func(self._value, *args, **kwargs))
        except Exception as e:
            return Nothing(e)


class Maybe:
    """A Maybe is a wrapper around a value that can be either Something or Nothing.
    It is used to represent a value that may or may not be present, and to handle errors in a functional way.
    """

    def __init__(self, value=None):
        if isinstance(value, Exception):
            self._value = Nothing(value)
        elif isinstance(value, Maybe):
            self._value = value._value
        elif value is None:
            self._value = Nothing()
        elif isinstance(value, (Nothing, Something)):
            self._value = value
        else:
            self._value = Something(value)

    def __call__(self, *args, **kwargs):
        return self._value(*args, **kwargs)

    def __getattr__(self, item):
        return getattr(self._value, item)

    def __getitem__(self, item):
        return self._value[item]

    def __contains__(self, item):
        return item in self._value

    def __bool__(self):
        return bool(self._value)

    def __eq__(self, other):
        if isinstance(other, (Maybe, Something)):
            return self._value == other._value
        elif isinstance(other, Nothing):
            return type(self._value) is Nothing
        else:
            return type(self._value) is type(other) and self._value == other

    def __repr__(self):
        return f"Maybe({self._value})"

    @property
    def exception(self):
        """Get the exception if the Maybe object is Nothing, otherwise return None.
        Returns:
        -------
        Exception or None
            The exception if the Maybe object is Nothing, otherwise None.
        """
        if type(self._value) is Nothing:
            return self._value.exception
        else:
            return None

    @property
    def value(self):
        """Get the value of the Maybe object if it is Something, otherwise return None.
        Returns:
        -------
        Any
            The value of the Maybe object if it is Something, otherwise None.
        """

        if type(self._value) is Something:
            return self._value.value
        else:
            return None

    def and_then(self, func, *args, **kwargs):
        """Apply a function to the value if it is Something, otherwise return Nothing.
        The function does not need to return a Maybe object, but it can.

        Parameters:
        ----------
        func : callable
            The function to be applied to the value.
        *args : tuple
            The positional arguments to be passed to the function after the value.
        **kwargs : dict
            The keyword arguments to be passed to the function.
        Returns:
        -------
        Maybe
            A Maybe object containing the result of the function or Nothing if the value is None or an exception occurred.
        """
        if type(self._value) is Something:
            try:
                return Maybe(func(self._value.value, *args, **kwargs))
            except Exception as e:
                return Maybe(e)
        else:
            return self


def lift(func):
    """Lifts a function to return a Maybe object.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            r = func(*args, **kwargs)
            if isinstance(r, Maybe):
                return r
            else:
                return Maybe(r)
        except Exception as e:
            return Maybe(e)

    return wrapper


class Thunk:
    """A Thunk is a callable that takes no arguments and returns a value.
    It is used to delay the evaluation of a function until it is called.
    This is useful for lazy evaluation, where we want to avoid computing a value until it is actually needed.
    It is also useful for creating a closure around a function and its arguments, so that we can call it later with the same arguments.
    """

    def __init__(self, func, *args, **kwargs):
        """Initialize the Thunk with a function and its arguments.

        Parameters:
        ----------
        func : callable
            The function to be called.
        *args : tuple
            The positional arguments to be passed to the function.
        **kwargs : dict
            The keyword arguments to be passed to the function.
        """
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def __call__(self):
        """Call the function with the stored arguments and keyword arguments.
        Returns:
        -------
        Any
            The result of the function call.
        """
        return self._func(*self._args, **self._kwargs)


def pipeline(*funcs):
    """Create a pipeline of functions that will be called in order.
    Each function will receive the result of the previous function as its first argument.
    This is useful for chaining functions together in a readable way.

    Parameters:
    ----------
    funcs : list of callable
        The functions to be called in order.

    Returns:
    -------
    callable
        A function that takes any number of arguments and keyword arguments and returns the result of the pipeline. 
        Those arguments will be passed to the first function in the pipeline. Note that the callable will return a Maybe object.

    Example:
    -------
    >>> def add(x, y):
    ...     return x + y
    >>> def multiply_by_2(x):
    ...     return x * 2
    >>> def subtract_3(x):
    ...     return x - 3
    >>> p = pipeline(add, multiply_by_2, subtract_3)
    >>> p(1, 2).value
    3
    """

    def wrapper(*args, __funcs=funcs, **kwargs):
        value = lift(__funcs[0])(*args, **kwargs)
        for func in __funcs[1:]:
            value = value.and_then(func)
        return value

    return wrapper


def combine_colors(color1: QColor, color2: QColor) -> QColor:
    r = (color1.red() + color2.red()) // 2
    g = (color1.green() + color2.green()) // 2
    b = (color1.blue() + color2.blue()) // 2
    a = (color1.alpha() + color2.alpha()) // 2
    return QColor(r, g, b, a)
