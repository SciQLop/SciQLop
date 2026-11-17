"""The state file is shared by every SciQLop window of the person: a window never writes back what
it read earlier, so two windows keep each other's changes."""
import cocat_rs
from PySide6.QtCore import QLockFile

from SciQLop.plugins.sciqlop_cocat.remembered import FILE_NAME, Remembered


def info(project_id: str, name: str = "A project"):
    return cocat_rs.ProjectInfo(project_id, name, "owner")


def ids(remembered: Remembered) -> list[str]:
    return [i.id for i in remembered.projects]


def test_two_windows_keep_each_other_s_changes(tmp_path):
    one, other = Remembered(tmp_path), Remembered(tmp_path)

    one.add_project(info("a"))
    other.set_left("x", True)
    one.note_tscat_imported()
    other.add_project(info("b"))
    one.follow({"id": "p", "name": "Public"})
    other.note_move_offered()

    for window in (one, other, Remembered(tmp_path)):
        assert ids(window) == ["a", "b"]
        assert window.left == {"x"}
        assert window.tscat_imported and window.move_offered
        assert [row["id"] for row in window.followed] == ["p"]


def test_a_window_sees_what_another_one_wrote_since(tmp_path):
    one, other = Remembered(tmp_path), Remembered(tmp_path)
    assert not one.tscat_imported

    other.note_tscat_imported()

    assert one.tscat_imported


def test_removing_a_project_keeps_the_ones_another_window_added(tmp_path):
    one, other = Remembered(tmp_path), Remembered(tmp_path)
    one.add_project(info("a"))
    other.add_project(info("b"))

    one.remove_project("a")
    one.unfollow("never followed")

    assert ids(other) == ["b"]


def test_a_project_is_listed_once(tmp_path):
    one, other = Remembered(tmp_path), Remembered(tmp_path)

    one.add_project(info("a"))
    other.add_project(info("a"))

    assert ids(one) == ["a"]


def test_two_windows_starting_at_once_make_one_first_project(tmp_path):
    one, other = Remembered(tmp_path), Remembered(tmp_path)

    first = one.projects_with_a_first(lambda: info("a", "My catalogues"))
    second = other.projects_with_a_first(lambda: info("b", "My catalogues"))

    assert [i.id for i in first] == [i.id for i in second] == ["a"]


def test_the_file_is_written_while_holding_its_lock(tmp_path, monkeypatch):
    remembered, held = Remembered(tmp_path), []

    def write(path, text):
        probe = QLockFile(str(tmp_path / f"{FILE_NAME}.lock"))
        held.append(not probe.tryLock(0))
        original(path, text)

    original = type(tmp_path).write_text
    monkeypatch.setattr(type(tmp_path), "write_text", write)

    remembered.note_tscat_imported()

    assert held == [True]


def test_without_a_folder_it_lasts_the_session(tmp_path):
    remembered = Remembered(None)

    remembered.add_project(info("a"))
    remembered.set_left("a", True)

    assert ids(remembered) == ["a"] and remembered.left == {"a"}


def test_an_unreadable_file_starts_afresh(tmp_path):
    (tmp_path / FILE_NAME).write_text("{ not json")

    remembered = Remembered(tmp_path)
    remembered.add_project(info("a"))

    assert ids(remembered) == ["a"]
