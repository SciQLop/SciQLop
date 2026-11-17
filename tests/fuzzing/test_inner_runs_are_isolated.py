"""A reproducer run in a child pytest must not share the parent's catalogue folders.

It did: a parent test that left a read open on the catalog database made the child fail with
"database is locked".
"""
from .inner_pytest import run_inner_pytest

PROBE = '''
from tests.fixtures import *  # noqa: F401,F403


def test_where(qapp):
    from SciQLop.components.storage import user_data_dir
    print("CHILD_CATALOGUES", user_data_dir("cocat_rs_local"))
'''


def test_the_child_has_its_own_catalogue_folders(qapp, tmp_path):
    from SciQLop.components.storage import user_data_dir
    probe = tmp_path / "test_probe.py"
    probe.write_text(PROBE)

    output = run_inner_pytest(probe).stdout

    assert "CHILD_CATALOGUES" in output
    assert f"CHILD_CATALOGUES {user_data_dir('cocat_rs_local')}" not in output
