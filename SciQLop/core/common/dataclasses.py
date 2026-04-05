from dataclasses import asdict, is_dataclass, fields
from typing import Any
import json


def to_json(obj: Any):
    assert is_dataclass(obj)
    return json.dumps(asdict(obj))


def from_dict(obj, d: dict):
    assert is_dataclass(obj)
    obj_fields = [f.name for f in fields(obj)]
    for key in d.keys():
        if key in obj_fields:
            setattr(obj, key, d[key])
        else:
            raise ValueError(f"Unknown key {key} in {type(obj)} spec")
    return obj


def from_json(obj, json_str: str):
    assert is_dataclass(obj)
    return from_dict(obj, json.loads(json_str))
