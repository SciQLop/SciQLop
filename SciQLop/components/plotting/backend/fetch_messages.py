"""Plain words for what a plot says when its data did not come.

A download that failed inside urllib3 reads "HTTPSConnectionPool(host=..., port=443): Max retries
exceeded with url: ..."; say which server and what happened instead. Any other error (a virtual
product's own message, a provider's) is already written for the user and is kept as it is.
"""
from typing import Iterator, Optional

from urllib3.exceptions import HTTPError, MaxRetryError, NewConnectionError, TimeoutError as Urllib3Timeout

_PREFIX = "Could not download the data: "
_ADVICE = "Check your connection, or try again later."


def _chain(exc: BaseException) -> Iterator[BaseException]:
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        yield exc
        exc = getattr(exc, "reason", None) if isinstance(exc, MaxRetryError) and exc.reason is not None \
            else (exc.__cause__ or exc.__context__)


def _timed_out(exc: BaseException) -> bool:
    # NewConnectionError (refused, no DNS) inherits from the connect-timeout class in urllib3.
    return isinstance(exc, Urllib3Timeout) and not isinstance(exc, NewConnectionError)


def _host(exc: BaseException) -> Optional[str]:
    return getattr(getattr(exc, "pool", None), "host", None) or getattr(exc, "host", None)


def describe_fetch_error(exc: BaseException) -> str:
    chain = list(_chain(exc))
    network = [e for e in chain if isinstance(e, HTTPError)]
    if not network:
        return str(exc)
    server = next((h for h in map(_host, network) if h), None) or "the server"
    happened = "took too long to answer" if any(map(_timed_out, network)) \
        else "could not be reached"
    return f"{_PREFIX}{server} {happened}. {_ADVICE}"


def no_data_message(name: str) -> str:
    return f"No data for {name} in this time range."
