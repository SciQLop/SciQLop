from .fixtures import *
import pytest


def test_color_for_uuid_returns_qcolor(qapp):
    from SciQLop.components.catalogs.backend.color_palette import color_for_catalog
    color = color_for_catalog("test-uuid-1234")
    from PySide6.QtGui import QColor
    assert isinstance(color, QColor)
    assert color.alpha() > 0


def test_color_is_consistent(qapp):
    from SciQLop.components.catalogs.backend.color_palette import color_for_catalog
    c1 = color_for_catalog("uuid-abc")
    c2 = color_for_catalog("uuid-abc")
    assert c1 == c2


def test_color_is_stable_across_hash_seeds(qapp):
    """color_for_catalog must not depend on PYTHONHASHSEED."""
    import subprocess, sys, os
    uuid = "550e8400-e29b-41d4-a716-446655440000"
    script = (
        "from SciQLop.components.catalogs.backend.color_palette import color_for_catalog; "
        f"c = color_for_catalog('{uuid}'); "
        "print(c.red(), c.green(), c.blue())"
    )
    results = set()
    for seed in ("0", "42", "12345"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        out = subprocess.check_output(
            [sys.executable, "-c", script], env=env, text=True
        ).strip()
        results.add(out)
    assert len(results) == 1, f"Color varies with PYTHONHASHSEED: {results}"


def test_different_uuids_can_differ(qapp):
    from SciQLop.components.catalogs.backend.color_palette import color_for_catalog
    colors = {color_for_catalog(f"uuid-{i}").name() for i in range(12)}
    # at least several distinct colors from 12 different UUIDs
    assert len(colors) >= 6
