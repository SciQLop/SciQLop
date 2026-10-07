"""Quitting while the catalog worker is busy must not abort SciQLop.

tscat_gui's TscatDriver.stop() waits 1 s for a worker that only stops after
quit(), then calls quit() without waiting: a worker still running an action
(opening the database at startup, a save) is destroyed while running and Qt
aborts the process ("QThread: Destroyed while thread is still running").
A batch script that ends right after startup hits it every time the database
open is slow.
"""
import time
from dataclasses import dataclass

from .fixtures import *  # noqa: F401,F403


def test_stop_waits_for_the_running_action(main_window):
    from tscat_gui.tscat_driver.actions import Action
    from tscat_gui.tscat_driver.driver import TscatDriver

    @dataclass
    class SlowAction(Action):
        def action(self) -> None:
            time.sleep(1.5)

    driver = TscatDriver()
    driver.do(SlowAction(user_callback=None))
    time.sleep(0.2)

    driver.stop()

    assert driver._worker.isFinished()
