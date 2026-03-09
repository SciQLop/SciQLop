from unittest.mock import MagicMock, call
from PySide6.QtCore import QProcess

from SciQLop.components.jupyter.jupyter_clients.clients_manager import ClientsManager


def _make_mock_client(running=True, terminate_succeeds=True):
    client = MagicMock()
    client.state.return_value = (
        QProcess.ProcessState.Running if running else QProcess.ProcessState.NotRunning
    )
    client.waitForFinished.side_effect = lambda msecs=-1: terminate_succeeds
    return client


def test_cleanup_terminates_gracefully_when_process_finishes_in_time():
    manager = ClientsManager.__new__(ClientsManager)
    client = _make_mock_client(running=True, terminate_succeeds=True)
    manager._jupyter_processes = [client]

    manager.cleanup()

    client.terminate.assert_called_once()
    client.kill.assert_not_called()
    client.waitForFinished.assert_called_once_with(3000)


def test_cleanup_escalates_to_kill_when_terminate_times_out():
    manager = ClientsManager.__new__(ClientsManager)
    client = _make_mock_client(running=True, terminate_succeeds=False)
    # First call (terminate wait) returns False, second call (kill wait) returns True
    client.waitForFinished.side_effect = [False, True]
    manager._jupyter_processes = [client]

    manager.cleanup()

    client.terminate.assert_called_once()
    client.kill.assert_called_once()
    assert client.waitForFinished.call_args_list == [call(3000), call(1000)]


def test_cleanup_skips_non_running_processes():
    manager = ClientsManager.__new__(ClientsManager)
    client = _make_mock_client(running=False)
    manager._jupyter_processes = [client]

    manager.cleanup()

    client.terminate.assert_not_called()
    client.kill.assert_not_called()
