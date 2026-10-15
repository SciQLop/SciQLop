"""Wires the sciqlop.kernel_namespace extension point to an EmbeddedJupyter kernel."""
from SciQLop.core.kernel_namespace import follow_kernel_namespace


def _poster(kernel_thread):
    """Runs on the kernel thread once it is up, immediately before; same rule as jupyqt's push."""
    def post(function, *args):
        loop = kernel_thread.loop
        if loop is None:
            function(*args)
        else:
            loop.call_soon_threadsafe(function, *args)
    return post


def follow_jupyter_namespace(jupyter) -> None:
    follow_kernel_namespace(jupyter.shell, _poster(jupyter.kernel_thread))
