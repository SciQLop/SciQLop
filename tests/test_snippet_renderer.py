import pytest


def test_format_product_path_joins_with_double_slash():
    from SciQLop.core.snippets import format_product_path
    assert format_product_path(["root", "speasy", "amda", "ACE", "b_gsm"]) \
        == "speasy//amda//ACE//b_gsm"


def test_format_product_path_keeps_path_when_no_root():
    from SciQLop.core.snippets import format_product_path
    assert format_product_path(["speasy", "amda", "b_gsm"]) \
        == "speasy//amda//b_gsm"


def test_format_product_path_handles_empty():
    from SciQLop.core.snippets import format_product_path
    assert format_product_path([]) == ""
    assert format_product_path(None) == ""


def test_format_product_path_single_segment():
    from SciQLop.core.snippets import format_product_path
    assert format_product_path(["root"]) == ""
    assert format_product_path(["b_gsm"]) == "b_gsm"


def test_format_product_path_preserves_inner_slash():
    """AMDA's product names contain ``/`` (e.g. ``"final / prelim"``).
    Single-slash joining would round-trip wrong via ``_split_path``."""
    from SciQLop.core.snippets import format_product_path
    from SciQLop.user_api.plot._plots import _split_path

    segments = ["root", "speasy", "amda", "ACE", "MFI", "final / prelim", "b_gsm"]
    rendered = format_product_path(segments)
    assert _split_path(rendered) == segments[1:], \
        f"round-trip broken: {rendered!r} -> {_split_path(rendered)!r}"


def test_render_snippet_loads_template_and_substitutes():
    from SciQLop.core.snippets import render_snippet
    out = render_snippet("_smoke.j2", name="world")
    assert out == "hello world\n"


def test_render_snippet_unknown_template_raises():
    import jinja2
    from SciQLop.core.snippets import render_snippet
    with pytest.raises(jinja2.TemplateNotFound):
        render_snippet("does_not_exist.j2")
