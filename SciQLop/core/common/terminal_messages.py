import re
from typing import Dict, List

SCIQLOP_MESSAGE_DELIMITER = "#SciQLop:"

SCIQLOP_MESSAGE_REGEX = re.compile(
    rf"{SCIQLOP_MESSAGE_DELIMITER}(?P<msg_type>\w+):(?P<action>\w+):(?P<uuid>[\w\d\-]*):(?P<title>[\w\d\-_]*)=(?P<msg>.*)")


def _sciqlop_message(type: str, action: str, uuid: str, title: str, value: str) -> str:
    return f"\n\n{SCIQLOP_MESSAGE_DELIMITER}{type}:{action}:{uuid}:{title}={value}\n\n"


def spawn_error_dialog(uuid: str, message: str, title: str = "SciQLop") -> str:
    return _sciqlop_message("error", "dialog", uuid, title, message)


def spawn_message_dialog(uuid: str, message: str, title: str = "SciQLop") -> str:
    return _sciqlop_message("message", "dialog", uuid, title, message)


def close_message_dialog(uuid: str) -> str:
    return _sciqlop_message("message", "close", uuid, "", "")


def spawn_progress_dialog(uuid: str, message: str, title: str = "SciQLop") -> str:
    return _sciqlop_message("progress", "dialog", uuid, title, message)


def update_progress_dialog(uuid: str, message: str, progress: int) -> str:
    return _sciqlop_message("progress", "update", uuid, message, str(progress))


def close_progress_dialog(uuid: str) -> str:
    return _sciqlop_message("progress", "close", uuid, "", "")


def parse_all_sciqlop_message(message: str) -> List[Dict]:
    return [m.groupdict() for m in SCIQLOP_MESSAGE_REGEX.finditer(message)]
