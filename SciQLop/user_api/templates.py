"""Public API for panel templates."""
from pathlib import Path

from SciQLop.components.plotting.panel_template import (
    PanelTemplate,
    list_templates as _list_templates,
    find_template as _find_template,
    delete_template as _delete_template,
    rename_template as _rename_template,
)


def load(name_or_path: str) -> PanelTemplate | None:
    p = Path(name_or_path)
    if p.suffix in ('.json', '.yaml', '.yml') and p.exists():
        return PanelTemplate.from_file(str(p))
    return _find_template(name_or_path)


def list_templates() -> list[PanelTemplate]:
    return _list_templates()


def delete(name: str) -> bool:
    return _delete_template(name)


def rename(old_name: str, new_name: str) -> bool:
    return _rename_template(old_name, new_name)
