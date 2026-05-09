"""Jinja2 environment for snippet templates.

Templates live next to this module under ``templates/``. Same convention as
``SciQLop/components/theming/stylesheet.py`` and ``core/web_channel_page.py``.
"""
from __future__ import annotations

import os
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
    undefined=StrictUndefined,
)


def render_snippet(template_name: str, **variables: Any) -> str:
    """Render a template under ``SciQLop/core/snippets/templates/``."""
    return _env.get_template(template_name).render(**variables)
