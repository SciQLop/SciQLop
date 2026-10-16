"""SearchDomain contract: describes a searchable topic/corpus for the smart
search registry. Deliberately plain (path_key, raw_text) pairs rather than a
live model-node reference, so index/query never need to touch a
Shiboken-wrapped C++ object on the hot per-query path."""
from operator import attrgetter
from typing import Iterable, NamedTuple, Protocol, runtime_checkable

from SciQLop.core.extensions import ExtensionPoint, declare


class NodeSnapshot(NamedTuple):
    path_key: str
    raw_text: str


@runtime_checkable
class SearchDomain(Protocol):
    name: str

    def snapshot(self) -> Iterable[NodeSnapshot]:
        ...


SEARCH_DOMAINS = declare(ExtensionPoint("sciqlop.search_domains", SearchDomain, what="search domain",
                                        key=attrgetter("name"), doc="Smart-search domains by name."))
