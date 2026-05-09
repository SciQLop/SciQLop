def test_format_product_path_joins_with_slash():
    from SciQLop.core.snippets import format_product_path
    assert format_product_path(["root", "speasy", "amda", "ACE", "b_gsm"]) \
        == "speasy/amda/ACE/b_gsm"


def test_format_product_path_keeps_path_when_no_root():
    from SciQLop.core.snippets import format_product_path
    assert format_product_path(["speasy", "amda", "b_gsm"]) \
        == "speasy/amda/b_gsm"


def test_format_product_path_handles_empty():
    from SciQLop.core.snippets import format_product_path
    assert format_product_path([]) == ""
    assert format_product_path(None) == ""


def test_format_product_path_single_segment():
    from SciQLop.core.snippets import format_product_path
    assert format_product_path(["root"]) == ""
    assert format_product_path(["b_gsm"]) == "b_gsm"
