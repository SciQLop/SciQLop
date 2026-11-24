"""What the tree's tooltips say about projects, catalogues and context-menu actions."""
from __future__ import annotations

from html import escape

from .public import PUBLIC_FOLDER as PUBLIC_FOLDER_NAME

STATES = {
    "synced": "Synced with the server",
    "connecting": "Connecting…",
    "offline": "Offline: your changes are sent once the server is back",
    "unauthorized": "The sign-in ended: sign in again",
    "no_access": "You no longer have access",
}

ACTIONS = {
    "Sign in…": "Sign in through your browser: your catalogues follow you, and you see projects shared with you",
    "Sign out": "Stop syncing; My catalogues stays usable from this computer",
    "Connect": "Load your projects from the server",
    "Reconnect": "Try the server again now",
    "New project…": "A project of yours, which you can share",
    "Open CoCat in browser": "The CoCat web app, which also manages groups",
    "Leave": "Hide this project here; Join brings it back",
    "Join": "Load this project and keep it in sync",
    "Save version…": "Name this point of the project's history, to restore or copy it later",
    "History…": "Who changed what and when; restore, name or copy a version",
    "Sharing…": "Who has access, with which role; invite people",
    "Import…": "Add catalogues from a VOTable, tscat JSON or TFCat file",
    "Import tscat catalogues": "Copy your tscat catalogues here; doing it again updates the same ones",
    "Open in browser": "This project in the CoCat web app",
    "Release": "Close this project in this window, so that another SciQLop window can open it",
    "Open here": "Open this project in this window; a project kept on this computer is open in one "
                 "SciQLop window at a time",
    "Export…": "Write this catalogue as VOTable, tscat JSON or TFCat",
    "Copy into a project…": "Copy this public catalogue into a project of yours, where you can edit it; or drag it onto a project",
    "Submit as a public catalogue…": "Offer a copy of it to the server's curators, to list under Public "
                                     "catalogues; or drag it onto Public catalogues",
    "Link into My catalogues": "Bookmark this catalogue in My catalogues > Linked; it stays in its own project",
    "Unlink": "Remove this link; the catalogue stays in its own project",
    "Unfollow": "Stop keeping this public catalogue up to date, and delete its copy on this computer; "
                "it stays listed",
}


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def _date(value) -> str:
    return f"{value:%Y-%m-%d}" if hasattr(value, "strftime") else str(value or "")[:10]


def _html(title: str, rows: list[tuple[str, str]], notes: list[str] = (), text: str = "") -> str:
    """Qt shows a tooltip as rich text when it starts with a tag; everything given is plain text."""
    table = "".join(f"<tr><td style='color:gray;padding-right:8px'>{escape(label)}</td>"
                    f"<td>{escape(value)}</td></tr>" for label, value in rows if value)
    paragraph = f"<p style='margin:4px 0'>{escape(text)}</p>" if text else ""
    hints = "".join(f"<br><i>{escape(note)}</i>" for note in notes)
    return f"<b>{escape(title)}</b>{paragraph}<table style='margin-top:4px'>{table}</table>{hints}"


def _span(events) -> str:
    """The time the events cover; `events` is sorted by start, as the provider keeps them."""
    if not events:
        return ""
    return f"{_date(events[0].start)} → {_date(max(e.stop for e in events))}"


def _contents(catalogues: int, smart: int, linked: int, events: int) -> str:
    kinds = [f"{smart} smart"] * bool(smart) + [f"{linked} linked"] * bool(linked)
    detail = f" ({', '.join(kinds)})" if kinds else ""
    return f"{_plural(catalogues, 'catalogue')}{detail}, {_plural(events, 'event')}"


def _sharing(info) -> str:
    if info.personal:
        return "your own project: only you see it"
    return "editors can invite people" if info.editors_can_share else "owners invite people"


def project_tip(info, *, state: str | None, local: bool, default: bool, catalogues: int,
                smart: int = 0, linked: int = 0, events: int = 0) -> str:
    """`state` is the sync state, or None when the project is not joined."""
    if local:
        rows = [("Stored", "on this computer only")]
    else:
        can_edit = info.role in ("owner", "editor")
        rows = [("Role", f"{info.role}, {'you can edit it' if can_edit else 'read-only'}"),
                ("Sync", STATES.get(state, state) if state else "not loaded"),
                ("Sharing", _sharing(info))]
    loaded = bool(state or local)
    if loaded:
        rows.append(("Contains", _contents(catalogues, smart, linked, events)))
    notes = ["Right-click > Join to load it"] * (not loaded)
    notes += ["New catalogues go here unless you choose a project"] * default
    return _html(info.name, rows, notes)


def closed_local_tip(name: str, elsewhere: bool) -> str:
    """A project kept on this computer that this window does not have open."""
    where = "Open in another SciQLop window" if elsewhere else "Not open in this window"
    note = ("Right-click > Open here, once the other window released it or closed" if elsewhere
            else "Right-click > Open here to load it")
    return _html(name, [("Stored", "on this computer only"), ("State", where)], [note])


def _origin(cocat_cat) -> str:
    """The catalogue it was copied from: the last hop of its chain."""
    chain = getattr(cocat_cat, "copied_from", None) or []
    if not chain:
        return ""
    hop = chain[-1]
    when = f", {_date(hop['at'])}" if hop.get("at") else ""
    by = f" by {hop['by']}" if hop.get("by") else ""
    return f"{hop['catalogue_name']} in {hop['project_name']}{when}{by}"


def unreadable_tip(name: str, error: str) -> str:
    return _html(name, [("Invalid rule", error)], ["This smart catalogue shows no events until its rule is fixed"])


def catalogue_tip(cocat_cat, events: list) -> str:
    shape = f"along {cocat_cat.shape_axis[0]} ({cocat_cat.shape_axis[1]})" if cocat_cat.shape_axis else ""
    rows = [("Events", _plural(len(events), "event")),
            ("Covers", _span(events)),
            ("By", cocat_cat.author or ""),
            ("Created", _date(cocat_cat.created) if cocat_cat.created else ""),
            ("Tags", ", ".join(sorted(getattr(cocat_cat, "tags", None) or [], key=str.lower))),
            ("Copied from", _origin(cocat_cat)),
            ("Shapes", shape)]
    notes = ["Smart catalogue: its events follow a rule, so they cannot be edited"] * (cocat_cat.rule is not None)
    return _html(cocat_cat.name, rows, notes)


def link_tip(name: str, link: dict, *, events: list | None, problem: str | None) -> str:
    """`events` None when the linked catalogue cannot be read; `problem` then says why."""
    rows = [("Linked from", link["project_name"]),
            ("Linked", " ".join(filter(None, [_date(link.get("at")) if link.get("at") else "",
                                              f"by {link['by']}" if link.get("by") else ""])))]
    if events is not None:
        rows += [("Events", _plural(len(events), "event")), ("Covers", _span(events))]
    return _html(name, rows, [problem or "Read-only here: edit it there"])


def provider_tip(description: str, signed_in_as: str | None, offline: bool, *, server: str = "",
                 projects: int = 0) -> str:
    if signed_in_as is None:
        return _html("CoCat", [("Server", server)], ["Not signed in: right-click > Sign in…"], description)
    rows = [("Account", signed_in_as), ("Server", server + (" (unreachable)" if offline else "")),
            ("Projects", str(projects))]
    return _html("CoCat", rows, text=description)


def public_folder_tip(listed: int) -> str:
    return _html(PUBLIC_FOLDER_NAME, [("Catalogues", f"{listed} listed")],
                 ["Select one to load it", "Drag one onto a project to copy it there",
                  "Drag one of yours here to submit it"],
                 "The server's public catalogues, read-only and kept up to date.")


def _relay(row: dict) -> list[tuple[str, str]]:
    relay = row.get("relay")
    if not relay:
        return []
    if not relay.get("published", True):
        return [("Source", f"{relay['source']}, no longer published")]
    return [("Source", relay["source"]), ("Refreshed", _date(relay.get("refreshed_at"))),
            ("Link", relay.get("url") or "")]


def public_tip(row: dict, *, state: str | None, events: list) -> str:
    """A listed public catalogue; `row` is the server's listing of it, `state` None until it is loaded."""
    if state:
        rows = [("Sync", STATES.get(state, state)), ("Events", _plural(len(events), "event")),
                ("Covers", _span(events))]
        notes = []
    else:
        count = row.get("count")
        rows = [("Events", _plural(count, "event") if count is not None else "")]
        notes = ["Not loaded: select it to load it"]
    rows = _relay(row) + [("Folder", row.get("folder") or "")] + rows
    return _html(row["name"], rows, notes + ["Public catalogue: read-only, kept up to date by the server"],
                 row.get("description") or "")
