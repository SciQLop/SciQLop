"""Minimal reproducer: QRhiWidget keeps a dangling QRhi pointer after leaving a top-level.

Steps:
  1. Show a QRhiWidget inside top-level window A and let it render.
  2. Move it into top-level window B and let it render there (it now uses B's QRhi).
  3. Move it out of B (setParent(None), stays hidden). QRhiWidget::event() handles
     WindowAboutToChangeInternal: it drops its cleanup callback on B's QRhi but keeps
     d->rhi pointing at it.
  4. Destroy window B, and B's QRhi with it. No callback is left to null d->rhi.
  5. Destroy the widget: ~QRhiWidget() calls d->rhi->removeCleanupCallback(this) on the
     freed QRhi, which is a use-after-free.

glibc usually hides the bad read, so run with MALLOC_PERTURB_ to poison freed memory:
    MALLOC_PERTURB_=165 python qrhiwidget_reparent_uaf.py          # crashes
    MALLOC_PERTURB_=165 python qrhiwidget_reparent_uaf.py control  # skips step 3, exits 0
On macOS arm64, pointer authentication catches it without any env var.
"""
import sys

import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QTimer
from PySide6.QtGui import QColor, QRhiDepthStencilClearValue
from PySide6.QtWidgets import QApplication, QRhiWidget, QVBoxLayout, QWidget


class ClearingRhiWidget(QRhiWidget):
    def render(self, cb):
        cb.beginPass(self.renderTarget(), QColor(40, 90, 160), QRhiDepthStencilClearValue(1.0, 0))
        cb.endPass()


def pump(ms=300):
    loop_until = QTimer()
    loop_until.setSingleShot(True)
    loop_until.start(ms)
    while loop_until.isActive():
        QApplication.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def top_level(title):
    w = QWidget()
    w.setWindowTitle(title)
    w.setLayout(QVBoxLayout())
    w.resize(400, 300)
    return w


def main(control: bool) -> int:
    app = QApplication(sys.argv)

    window_a = top_level("A")
    rhi_widget = ClearingRhiWidget()
    window_a.layout().addWidget(rhi_widget)
    window_a.show()
    pump()
    print("rendered in A", flush=True)

    window_b = top_level("B")
    window_b.layout().addWidget(rhi_widget)
    window_b.show()
    pump()
    print("rendered in B", flush=True)

    if not control:
        rhi_widget.setParent(None)
        print("moved out of B (hidden, not re-rendered)", flush=True)

    window_b.deleteLater()
    pump()
    print("B destroyed", flush=True)

    if shiboken6.isValid(rhi_widget):
        rhi_widget.deleteLater()
        pump()
    print("widget destroyed, no crash", flush=True)

    window_a.deleteLater()
    pump()
    return 0


if __name__ == "__main__":
    sys.exit(main(control="control" in sys.argv[1:]))
