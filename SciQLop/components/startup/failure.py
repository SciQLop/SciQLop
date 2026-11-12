"""Plain words for a failed workspace preparation, shown with the traceback."""

_NETWORK_MARKERS = (
    "dns error", "error sending request", "failed to fetch", "could not connect", "connection refused",
    "connection reset", "timed out", "name resolution", "network is unreachable", "tls handshake",
    "certificate", "proxy",
)

_NETWORK = (
    "SciQLop could not download the packages this workspace needs.\n"
    "The first start of a workspace needs the network. Check your connection and start SciQLop again. "
    "Behind a proxy, set the HTTPS_PROXY environment variable, or the proxy in SciQLop's Settings "
    "(Application > Network) from a workspace that starts."
)

_OTHER = (
    "SciQLop could not prepare this workspace.\n"
    "The details are in the error text. Resetting the environment rebuilds the workspace's packages and "
    "keeps your notebooks and files: use the launcher's \"Reset environment\" button, or start with "
    "sciqlop --reset-environment."
)


def explain_preparation_failure(details: str) -> str:
    lowered = details.lower()
    return _NETWORK if any(marker in lowered for marker in _NETWORK_MARKERS) else _OTHER
