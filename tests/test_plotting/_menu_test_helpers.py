"""Shared QMenu introspection helpers for the panel context-menu tests
(structure/mnemonic/shortcut-hint checks live in several test_panel_*.py
files that all need the same raw-QAction-text parsing)."""


def display_text(raw_text):
    """QAction.text() as the user reads it: '&&' -> literal '&', a lone
    '&' (mnemonic marker) dropped, shortcut hint after '\\t' stripped."""
    body = raw_text.split("\t", 1)[0]
    return body.replace("&&", "\0").replace("&", "").replace("\0", "&")


def mnemonic_letter(raw_text):
    """The explicit &-mnemonic letter from a raw QAction text, or None."""
    body = raw_text.split("\t", 1)[0]
    i = 0
    while i < len(body):
        if body[i] == "&":
            if body[i:i + 2] == "&&":
                i += 2
                continue
            return body[i + 1].lower() if i + 1 < len(body) else None
        i += 1
    return None


def submenu(menu, title):
    for a in menu.actions():
        sub = a.menu()
        if sub is not None and display_text(a.text()) == title:
            return sub
    return None


def submenu_titles(menu):
    return [display_text(a.text()) for a in menu.actions() if a.menu() is not None]


def leaf_labels(menu):
    return [display_text(a.text()) for a in menu.actions()
            if a.menu() is None and not a.isSeparator()]


def find_action(menu, text):
    for a in menu.actions():
        if display_text(a.text()) == text:
            return a
    return None
