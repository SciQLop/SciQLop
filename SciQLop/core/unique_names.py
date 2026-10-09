import itertools

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


def claim_name(name: str) -> str:
    """
    Reserve `name`, or `name_1`, `name_2`... when it is already taken.
    """
    candidates = (name if i == 0 else f'{name}_{i}' for i in itertools.count())
    unique = next(c for c in candidates if c not in _all_reserved_names_)
    reserve_name(unique)
    return unique


def auto_name(base: str, sep: str = "", name=None) -> str:
    """
    Either claim a unique name from `name` or create a new one based on the base name.
    """
    if name is None:
        return make_simple_incr_name(base, sep=sep)
    return claim_name(name)
