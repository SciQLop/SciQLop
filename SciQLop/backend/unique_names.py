_used_names_ = {}


def make_simple_incr_name(base: str, sep: str = "") -> str:
    index = _used_names_.get(base, 0)
    _used_names_[base] = index + 1
    return f'{base}{sep}{index}'
