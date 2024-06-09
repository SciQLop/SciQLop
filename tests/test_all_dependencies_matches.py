import os
import platform
from SciQLop import sciqlop_dependencies

try:
    import tomllib
except ImportError:
    from pip._vendor import tomli as tomllib

__here__ = os.path.dirname(os.path.abspath(__file__))


def dependencies_from_pyproject() -> list:
    with open(os.path.join(__here__, "..", "pyproject.toml"), "r") as f:
        data = tomllib.loads(f.read())
    return data["project"]["dependencies"]


def filter_comments(lines: list) -> list:
    return list(map(lambda l: l.split('#')[0], filter(lambda l: not l.startswith('#'), map(str.strip, lines))))


def all_lower_case(l: list) -> list:
    return list(map(str.lower, l))


def dependencies_from_requirements() -> list:
    with open(os.path.join(__here__, "..", "requirements.txt"), "r") as f:
        return filter_comments(f.readlines())


def test_all_dependencies_matches():
    assert set(all_lower_case(dependencies_from_pyproject())) == set(
        all_lower_case(dependencies_from_requirements())) and set(all_lower_case(sciqlop_dependencies())) == set(
        all_lower_case(dependencies_from_requirements()))
