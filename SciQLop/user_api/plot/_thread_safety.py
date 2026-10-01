"""Thread-safety primitives for the plot user_api."""
from SciQLop.user_api.threading import on_main_thread, MainThreadProxy, _on_main_thread


class GuardedImpl:
    """Mixin keeping the wrapped Qt object off the kernel thread.

    ``_impl`` is the raw object on the GUI thread, where every ``@on_main_thread``
    method reads it. Elsewhere it is a MainThreadProxy: kernel cells reaching into
    ``obj._impl`` get marshaled calls instead of a segfault (SciQLop#147).
    Proxying rather than raising follows ``sciqlop_app()``, so such code keeps working.
    """

    @property
    def _impl(self):
        impl = self.__dict__.get("_GuardedImpl__impl")
        if impl is None or _on_main_thread():
            return impl
        return MainThreadProxy(impl)

    @_impl.setter
    def _impl(self, value):
        self.__impl = value


__all__ = ["on_main_thread", "GuardedImpl"]
