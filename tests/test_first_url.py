import pytest

from SciQLop.components.catalogs.ui.link_text import first_url


@pytest.mark.parametrize("text, expected", [
    ("https://doi.org/10.1029/2005JA011284", "https://doi.org/10.1029/2005JA011284"),
    ("  https://doi.org/10.1029/2005JA011284  ", "https://doi.org/10.1029/2005JA011284"),
    ("http://example.org/paper", "http://example.org/paper"),
    ("HTTPS://example.org/paper", "HTTPS://example.org/paper"),
    ("See https://example.org/paper for details", "https://example.org/paper"),
    ("https://example.org/paper, Smith 2005", "https://example.org/paper"),
    ("(https://example.org/paper).", "https://example.org/paper"),
    ("paper: https://example.org/paper;", "https://example.org/paper"),
    ('<a href="https://example.org/paper">x</a>', "https://example.org/paper"),
    ("https://example.org/a https://example.org/b", "https://example.org/a"),
    ("https://a.org/x, https://b.org/y", "https://a.org/x"),
    ("https://en.wikipedia.org/wiki/Foo_(bar)", "https://en.wikipedia.org/wiki/Foo_(bar)"),
    ("(see https://en.wikipedia.org/wiki/Foo_(bar))", "https://en.wikipedia.org/wiki/Foo_(bar)"),
    ("https://example.org/search?q=a&b=c#frag", "https://example.org/search?q=a&b=c#frag"),
    ("«https://example.org/paper»", "https://example.org/paper"),
    ("“https://example.org/paper”", "https://example.org/paper"),
    ("https://example.org/paper。", "https://example.org/paper"),
    ("https://example.org/paper，", "https://example.org/paper"),
    ("https://example.org/paper…", "https://example.org/paper"),
])
def test_first_url_extracts_the_link_from_the_text(text, expected):
    assert first_url(text) == expected


@pytest.mark.parametrize("text", [
    "",
    "no link here",
    "10.1029/2005JA011284",
    "doi:10.1029/2005JA011284",
    "www.example.org/paper",
    "ftp://example.org/file",
    "mailto:someone@example.org",
    "https://",
    "https://.",
    None,
    42,
])
def test_first_url_is_none_when_there_is_no_http_link(text):
    assert first_url(text) is None
