# tests/test_plugin_resolver.py
"""Plugin load order from plugin.json dependencies (spec §3.2): deterministic, refusals named."""
from SciQLop.components.plugins.backend.loader.resolver import Candidate, resolve


def _c(id, version="1.0.0", deps=(), opt=()):
    return Candidate(id, version, tuple(deps), tuple(opt))


def test_dependencies_load_first_ties_by_name():
    r = resolve({"study": _c("study", deps=["vdf", "earth"]), "vdf": _c("vdf"), "earth": _c("earth"),
                 "aaa": _c("aaa")})
    assert r.order == ("aaa", "earth", "vdf", "study") and r.refused == {}


def test_missing_dependency_refuses_and_cascades():
    r = resolve({"study": _c("study", deps=["vdf"]), "user": _c("user", deps=["study"])})
    assert r.order == ()
    assert r.refused["study"] == "needs plugin 'vdf', which is not installed or not enabled"
    assert r.refused["user"] == "needs plugin 'study', which was refused: needs plugin 'vdf', " \
                                "which is not installed or not enabled"


def test_out_of_range_version_is_refused_with_both_versions():
    r = resolve({"study": _c("study", deps=["vdf>=1.2,<2"]), "vdf": _c("vdf", "2.0.0")})
    assert r.order == ("vdf",)
    assert r.refused["study"] == "needs plugin vdf>=1.2,<2, but vdf 2.0.0 is installed"


def test_present_optional_dependency_is_ordered_first_absent_one_ignored():
    r = resolve({"earth": _c("earth", opt=["mars", "pluto"]), "mars": _c("mars")})
    assert r.order == ("mars", "earth") and r.declared["earth"] == frozenset({"mars", "pluto"})
    assert r.required["earth"] == frozenset()


def test_cycle_members_are_refused():
    r = resolve({"a": _c("a", deps=["b"]), "b": _c("b", deps=["a"]), "c": _c("c")})
    assert r.order == ("c",)
    assert r.refused["a"] == r.refused["b"] == "dependency cycle between a, b"


def test_dependents_of_a_cycle_get_the_cascade_message():
    r = resolve({"a": _c("a", deps=["b"]), "b": _c("b", deps=["a"]), "d": _c("d", deps=["a"])})
    assert r.order == ()
    assert r.refused["a"] == r.refused["b"] == "dependency cycle between a, b"
    assert r.refused["d"] == "needs plugin 'a', which was refused: dependency cycle between a, b"


def test_optional_edge_against_a_required_one_is_not_a_cycle():
    r = resolve({"vdf": _c("vdf", opt=["mars"]), "mars": _c("mars", deps=["vdf"])})
    assert r.order == ("vdf", "mars") and r.refused == {}


def test_mutual_optional_dependencies_are_not_a_cycle():
    r = resolve({"b": _c("b", opt=["a"]), "a": _c("a", opt=["b"])})
    assert r.order == ("a", "b") and r.refused == {}


def test_optional_cycle_keeps_other_optional_orderings():
    r = resolve({"a": _c("a", opt=["b"]), "b": _c("b", opt=["a"]), "c": _c("c", opt=["z"]), "z": _c("z")})
    assert r.order.index("z") < r.order.index("c") and r.refused == {}


def test_already_active_plugins_satisfy_dependencies():
    r = resolve({"study": _c("study", deps=["vdf>=1"])}, active={"vdf": "1.3.0"})
    assert r.order == ("study",)


def test_invalid_specifier_is_refused():
    r = resolve({"study": _c("study", deps=["vdf >>> 1"])})
    assert r.refused["study"].startswith("invalid dependency 'vdf >>> 1'")


def test_dependency_name_matches_across_dash_underscore_and_case():
    from SciQLop.components.plugins.backend.loader.resolver import Candidate, resolve
    r = resolve({"planetary_scenes": Candidate("planetary_scenes", "1.0.0"),
                 "study": Candidate("study", "1.0.0", ("Planetary-Scenes>=1",))})
    assert r.refused == {}
    assert r.order == ("planetary_scenes", "study")
    assert r.declared["study"] == frozenset({"planetary_scenes"})


def test_normalized_name_also_matches_an_active_plugin():
    from SciQLop.components.plugins.backend.loader.resolver import Candidate, resolve
    r = resolve({"study": Candidate("study", "1.0.0", ("my-dep",))}, active={"my_dep": "2.0"})
    assert r.refused == {} and r.order == ("study",)


def test_loosening_an_optional_cycle_keeps_edges_to_plugins_outside_it():
    from SciQLop.components.plugins.backend.loader.resolver import Candidate, resolve
    r = resolve({"a": Candidate("a", "1", (), ("b", "z")),
                 "b": Candidate("b", "1", (), ("a",)),
                 "z": Candidate("z", "1")})
    assert r.refused == {}
    assert r.order.index("z") < r.order.index("a")
