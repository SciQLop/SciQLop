import re
from typing import Dict, List

SCIQLOP_MESSAGE_DELIMITER = "#SciQLop:"

SCIQLOP_MESSAGE_REGEX = re.compile(
    rf"{SCIQLOP_MESSAGE_DELIMITER}(?P<msg_type>\w+):(?P<action>\w+):(?P<uuid>[\w\d\-]*):(?P<title>[\w\d\-_]*)=(?P<msg>.*)")


def parse_all_sciqlop_message(message: str) -> List[Dict]:
    return [m.groupdict() for m in SCIQLOP_MESSAGE_REGEX.finditer(message)]
