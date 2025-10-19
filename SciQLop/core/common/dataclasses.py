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


def _from_json_obj(obj: Any, json_str):
    d = json.loads(json_str)
    return from_dict(obj, d)


def _from_json(cls, json_str):
    return _from_json_obj(cls(), json_str)


def from_json(*args):
    assert len(args) == 2
    assert type(args[1]) is str
    if type(args[0]) is type:
        return lambda json_str: _from_json(args[0], args[1])
    elif is_dataclass(args[0]):
        return _from_json_obj(args[0], args[1])
