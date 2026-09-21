"""Human readable byte sizes.

Parsing reuses pydantic's ``ByteSize`` (decimal and binary units, plain
numbers as bytes); formatting is decimal with a space and no trailing
``.0`` so the Speasy default 20000000000 renders as ``20 GB``.
"""

from pydantic import ByteSize, TypeAdapter

_adapter = TypeAdapter(ByteSize)


def parse_byte_size(text: str) -> int:
    """Parse '500MB', '1.5 GB', '2 TiB' or plain bytes into an int."""
    return int(_adapter.validate_python(str(text).strip()))


def is_byte_size(text: str) -> bool:
    try:
        parse_byte_size(text)
    except ValueError:
        return False
    return True


def format_byte_size(value: int) -> str:
    """Format bytes as decimal, e.g. 20000000000 -> '20 GB'."""
    return (
        ByteSize(int(value))
        .human_readable(decimal=True, separator=" ")
        .replace(".0 ", " ")
    )
