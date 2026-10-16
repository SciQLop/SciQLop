"""Panel template file formats: the sciqlop.template_formats extension point (Tier 3 spec §4.1)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from SciQLop.core.extensions import ExtensionPoint, declare, owned_by
from SciQLop.core.name_follower import CORE_OWNER


@dataclass(frozen=True)
class TemplateFormat:
    id: str
    label: str
    suffixes: tuple[str, ...]
    loads: Callable[[str], dict]
    dumps: Callable[[dict], str]


TEMPLATE_FORMATS = declare(ExtensionPoint("sciqlop.template_formats", TemplateFormat, what="template format",
                                          doc="Panel template file formats by id; each lists its suffixes."))


def template_suffixes() -> tuple[str, ...]:
    return tuple(s for fmt in TEMPLATE_FORMATS.list() for s in fmt.suffixes)


def format_for(path: Path) -> TemplateFormat:
    fmt = next((f for f in TEMPLATE_FORMATS.list() if path.suffix in f.suffixes), None)
    if fmt is None:
        raise ValueError(f"Unsupported file extension: {path.suffix} (supported: {', '.join(template_suffixes())})")
    return fmt


def file_dialog_filter() -> str:
    return f"Templates ({' '.join(f'*{s}' for s in template_suffixes())})"


def _load_yaml(text: str):
    """Templates saved before 0.14.2 wrote ranges as !!python/tuple, which
    safe_load rejects; read those as plain lists."""
    import yaml

    class Loader(yaml.SafeLoader):
        pass

    Loader.add_constructor("tag:yaml.org,2002:python/tuple", Loader.construct_sequence)
    return yaml.load(text, Loader=Loader)


def _dump_yaml(tree: dict) -> str:
    import yaml
    return yaml.dump(tree, default_flow_style=False, sort_keys=False)


with owned_by(CORE_OWNER):
    TEMPLATE_FORMATS.contribute(TemplateFormat("json", "JSON", (".json",), loads=json.loads,
                                               dumps=lambda tree: json.dumps(tree, indent=2)))
    TEMPLATE_FORMATS.contribute(TemplateFormat("yaml", "YAML", (".yaml", ".yml"), loads=_load_yaml,
                                               dumps=_dump_yaml))
