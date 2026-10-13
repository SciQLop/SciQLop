"""Thread-safety primitives for the plot user_api."""
from SciQLop.user_api.threading import on_main_thread, main_thread_safe


class GuardedImpl:
    """Mixin keeping the wrapped Qt object off the kernel thread.

    ``_impl`` is the raw object on the GUI thread, where every ``@on_main_thread``
    method reads it. Elsewhere it is a MainThreadProxy: kernel cells reaching into
    ``obj._impl`` get marshaled calls instead of a segfault (SciQLop#147).
    Proxying rather than raising follows ``sciqlop_app()``, so such code keeps working.
    """

    @property
    def _impl(self):
        return main_thread_safe(self.__dict__.get("_GuardedImpl__impl"))

    @_impl.setter
    def _impl(self, value):
        self.__impl = value


def _same(value):
    return value


def _wrapped_impl(wrapper):
    return wrapper._get_impl_or_raise()


def _qt_property(getter: str, setter: str, *, to_qt=_same, from_qt=_same, of=_wrapped_impl,
                doc: str = ""):
    """A property forwarding to ``getter()`` / ``setter(value)`` on a Qt object,
    on the GUI thread. ``of(wrapper)`` picks that object (the wrapped impl by
    default); ``to_qt`` / ``from_qt`` convert the value on the way in / out."""

    @on_main_thread
    def fget(self):
        return from_qt(getattr(of(self), getter)())

    @on_main_thread
    def fset(self, value):
        getattr(of(self), setter)(to_qt(value))

    return property(fget, fset, doc=doc)


__all__ = ["on_main_thread", "GuardedImpl"]
