"""What dropping something on a plot does: the sciqlop.drop_rules extension point (spec §4.3)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from SciQLop.core.extensions import ExtensionPoint, declare


@dataclass(frozen=True)
class DropRule:
    id: str
    mime_type: str
    drop: Callable[[Any, Any, Any], Any]   # (plot or None, payload, panel); product drops get one product path
    product_kind: Optional[str] = None     # product-list drops: the dragged product's kind; None = any
    target: Optional[str] = None           # plot kind of the plot dropped on; None = any
    creates_plot: bool = False             # a drop between plots makes a new plot for it


DROP_RULES = declare(ExtensionPoint("sciqlop.drop_rules", DropRule, what="drop rule",
                                    doc="What a drop of one MIME type does, by product kind and target plot kind."))


def _weight(rule: DropRule) -> int:
    return 2 * (rule.product_kind is not None) + (rule.target is not None)


def rule_for(mime_type: str, product_kind: Optional[str], target: Optional[str]) -> Optional[DropRule]:
    """The most specific rule: a matching product kind outweighs a matching target; ties go to the smallest id."""
    matching = [r for r in DROP_RULES.list() if r.mime_type == mime_type
                and r.product_kind in (None, product_kind) and r.target in (None, target)]
    return min(matching, key=lambda r: (-_weight(r), r.id), default=None)
