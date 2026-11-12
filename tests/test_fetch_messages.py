"""A failed download says what happened in plain words; other errors keep their own text."""
import pytest
import urllib3
from urllib3.exceptions import (ConnectTimeoutError, MaxRetryError, NameResolutionError,
                                NewConnectionError, ReadTimeoutError)

from SciQLop.components.plotting.backend.fetch_messages import describe_fetch_error, no_data_message

_POOL = urllib3.HTTPSConnectionPool("amda.irap.omp.eu")
_URL = "/php/rest/getParameter.php"


def _gave_up(reason):
    return MaxRetryError(_POOL, _URL, reason)


@pytest.mark.parametrize("exc, expected", [
    (_gave_up(NewConnectionError(None, "Connection refused")), "amda.irap.omp.eu could not be reached"),
    (_gave_up(NameResolutionError("amda.irap.omp.eu", None, OSError("no dns"))),
     "amda.irap.omp.eu could not be reached"),
    (_gave_up(ConnectTimeoutError(_POOL, "timed out")), "amda.irap.omp.eu took too long to answer"),
    (ReadTimeoutError(_POOL, _URL, "read timed out"), "amda.irap.omp.eu took too long to answer"),
    (_gave_up(None), "amda.irap.omp.eu could not be reached"),
])
def test_a_network_failure_is_said_plainly(exc, expected):
    message = describe_fetch_error(exc)
    assert message.startswith("Could not download the data: ")
    assert expected in message
    assert "HTTPSConnectionPool" not in message and "Max retries" not in message


def test_a_network_failure_wrapped_in_another_error_is_still_recognised():
    try:
        try:
            raise _gave_up(ConnectTimeoutError(_POOL, "timed out"))
        except MaxRetryError as inner:
            raise RuntimeError("request failed") from inner
    except RuntimeError as outer:
        assert "took too long to answer" in describe_fetch_error(outer)


def test_any_other_error_keeps_its_own_text():
    assert describe_fetch_error(ValueError("Declared vector (3 components) but got shape (10, 2)")) == \
        "Declared vector (3 components) but got shape (10, 2)"


def test_no_data_message_names_the_product():
    assert no_data_message("b_gse") == "No data for b_gse in this time range."
