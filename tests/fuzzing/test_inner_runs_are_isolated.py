"""A reproducer run in a child pytest must not share the parent's catalog database.

It did: a parent test that left a read open on it made the child fail with "database is locked".
"""
from .inner_pytest import run_inner_pytest

PROBE = '''
from tests.fixtures import *  # noqa: F401,F403


def test_where(qapp):
    from tscat.base import backend
    print("CHILD_DATABASE", backend().session.get_bind().url)
'''


def test_the_child_has_its_own_catalog_database(qapp, tmp_path):
    from tscat.base import backend
    probe = tmp_path / "test_probe.py"
    probe.write_text(PROBE)

    output = run_inner_pytest(probe).stdout

    assert "CHILD_DATABASE" in output
    assert f"CHILD_DATABASE {backend().session.get_bind().url}" not in output
