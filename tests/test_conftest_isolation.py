"""The test session reads the user's speasy settings but must never write them.

conftest used to symlink ~/.config/speasy into the session's config dir, so
speasy saving its resolved cache path (the session's temp dir) rewrote the
user's real config.ini: every later SciQLop or speasy session then cached
into a deleted-on-reboot /tmp directory instead of ~/.cache/speasy."""
from pathlib import Path

from tests.conftest import _test_tmp


def test_speasy_config_file_lives_in_the_session_temp_dir():
    import speasy.config
    config_file = Path(speasy.config.SPEASY_CONFIG_FILE).resolve()
    assert config_file.is_relative_to(_test_tmp.resolve())
