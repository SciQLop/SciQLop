_used_names_ = {}
_all_reserved_names_ = set()


def reserve_name(name: str) -> None:
    """
    Reserve a name so that it cannot be used again.
    """
    _all_reserved_names_.add(name)


def release_name(name: str) -> None:
    """
    Release a previously reserved name so it can be reused.
    """
    _all_reserved_names_.discard(name)


def make_simple_incr_name(base: str, sep: str = "") -> str:
    index = _used_names_.get(base, 0)
    while f'{base}{sep}{index}' in _all_reserved_names_:
        index += 1
    name = f'{base}{sep}{index}'
    _used_names_[base] = index + 1
    _all_reserved_names_.add(name)
    return name


def auto_name(base: str, sep: str = "", name=None) -> str:
    """
    Either reserve a name or create a new one based on the base name.
    """
    if name is None:
        return make_simple_incr_name(base, sep=sep)
    else:
        reserve_name(name)
        return name
