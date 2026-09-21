import re

_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_TRAILING_PUNCTUATION = ".,;:!?…。，»”’"
_OPENERS = {")": "(", "]": "[", "}": "{"}


def first_url(text) -> str | None:
    """The first http(s) link in `text`, without the punctuation that surrounds it in prose."""
    if not isinstance(text, str):
        return None
    match = _URL.search(text)
    if match is None:
        return None
    url = _trim(match.group())
    return url if url.partition("://")[2] else None


def _trim(url: str) -> str:
    while url and (url[-1] in _TRAILING_PUNCTUATION or _is_unbalanced_closer(url)):
        url = url[:-1]
    return url


def _is_unbalanced_closer(url: str) -> bool:
    opener = _OPENERS.get(url[-1])
    return opener is not None and url.count(url[-1]) > url.count(opener)
