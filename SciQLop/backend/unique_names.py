_all_names_ = set()
_used_names_ = {}


def make_simple_incr_name(base: str, sep: str = "") -> str:
    while True:
        index = _used_names_.get(base, 0)
        _used_names_[base] = index + 1
        res = f'{base}{sep}{index}'
        if res not in _all_names_:
            return res


def set_name(name: str) -> None:
    _all_names_.add(name)
