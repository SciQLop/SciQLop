"""Guide: share a catalogue project with someone, from SciQLop.

    python -m SciQLop.components.guides.authoring.core.share_a_catalog_project OUT_DIR      -> OUT_DIR/share-a-catalog-project.svg

Verified in the code: a project on the CoCat server shows under "Shared" in the catalogue tree
(sciqlop_cocat/sections.py). Its right-click menu has "Sharing…" when signed in and online, except for
the account's own project, which the server refuses to share (provider.py, folder_actions). The window
(sharing_dialog.py) lists the members, has an "Invite" box (email, role, Invite) and "Pending
invitations"; an invitation shows its link with "Copy link". Only people allowed to share see the
Invite box. The members' table and the dates come from the server: those drawn here are made up.
"""
import sys
from pathlib import Path

from SciQLop.components.catalogs.backend.provider import Section
from SciQLop.components.catalogs.ui.catalog_tree import SECTION_ICONS, SECTION_LABELS
from SciQLop.components.guides.authoring import kit
from SciQLop.plugins.sciqlop_cocat.sharing import ASSIGNABLE_ROLES

P, T = "sqs", 14.0
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
clock = kit.Clock(T)
HOME, PROJECT = (600, 300), (140, 187)
MENU_X, MENU_Y, MENU_W = 146, 196, 226
MENU_ROWS = [kit.ui(r) for r in ("Leave", "Save version of the whole project…", "History…", "Sharing…", "Import…")]
SHARING = (MENU_X + 50, MENU_Y + 18 + 22 * 3 - 4)
DX, DY, DW, DH = 232, 62, 420, 288
FIELD, INVITE = (DX + 130, DY + 107), (DX + DW - 40, DY + 107)
RIGHT_CLICK, CHOOSE, TYPE, SEND, CLOSE, RESET = 1.8, 3.2, 4.8, 6.9, 12.2, 12.8
VIEWER = ASSIGNABLE_ROLES[1]

STYLE = kit.base_style(P, f"{T:g}s") + f"""
/* Resting state = the result: the Sharing window with the invitation pending. */
.{P} .cursor {{ animation-name: {P}-cursor; opacity: 0; }}
.{P} .menu {{ animation-name: {P}-menu; opacity: 0; }}
.{P} .key {{ animation-name: {P}-key; opacity: 0; }}
.{P} .dialog {{ animation-name: {P}-dialog; }}
.{P} .placeholder {{ animation-name: {P}-placeholder; opacity: 0; }}
.{P} .typed1 {{ animation-name: {P}-typed1; opacity: 0; }}
.{P} .typed2 {{ animation-name: {P}-typed2; opacity: 0; }}
.{P} .focus {{ animation-name: {P}-focus; opacity: 0; }}
.{P} .sent {{ animation-name: {P}-sent; }}
""" + "".join(f".{P} .{n} {{ animation-name: {P}-{n}; }}\n" for n in ("rc", "choose", "field", "send", "s1", "s2", "s3")) \
    + kit.keyframes(f"{P}-cursor", clock.path([(0, HOME), (0.6, HOME), (1.5, PROJECT), (2.4, PROJECT), (3.0, SHARING), (3.6, SHARING),
                                               (4.4, FIELD), (6.3, FIELD), (6.8, INVITE), (11.6, INVITE), (T, HOME)], lambda t: "opacity: 1;")) \
    + kit.keyframes(f"{P}-menu", clock.shown((RIGHT_CLICK + 0.1, CHOOSE), fade=0.15)) \
    + kit.keyframes(f"{P}-key", clock.shown((RIGHT_CLICK - 0.4, RIGHT_CLICK + 0.5), fade=0.2)) \
    + kit.keyframes(f"{P}-dialog", clock.shown((CHOOSE + 0.1, CLOSE), fade=0.25)) \
    + kit.keyframes(f"{P}-placeholder", clock.shown((0, TYPE), fade=0.05)) \
    + kit.keyframes(f"{P}-typed1", clock.shown((TYPE, TYPE + 0.5), fade=0.05)) \
    + kit.keyframes(f"{P}-typed2", clock.shown((TYPE + 0.5, SEND + 0.1), fade=0.05)) \
    + kit.keyframes(f"{P}-focus", clock.shown((4.5, SEND), fade=0.1)) \
    + kit.keyframes(f"{P}-sent", clock.shown((SEND + 0.3, RESET), fade=0.3)) \
    + kit.keyframes(f"{P}-rc", clock.pulse(RIGHT_CLICK)) + kit.keyframes(f"{P}-choose", clock.pulse(CHOOSE)) \
    + kit.keyframes(f"{P}-field", clock.pulse(4.5)) + kit.keyframes(f"{P}-send", clock.pulse(SEND)) \
    + kit.keyframes(f"{P}-s1", clock.lit((0.6, 3.6))) + kit.keyframes(f"{P}-s2", clock.lit((3.9, SEND + 0.2))) \
    + kit.keyframes(f"{P}-s3", clock.lit((SEND + 0.4, CLOSE)))

ROWS = (kit.section_row(106, SECTION_ICONS[Section.MINE], kit.ui(SECTION_LABELS[Section.MINE]), "closed")
        + kit.section_row(134, SECTION_ICONS[Section.SHARED], kit.ui(SECTION_LABELS[Section.SHARED]))
        + kit.tree_row(162, 1, "Solar wind survey", "closed", cls="dim")
        + kit.tree_row(190, 1, "Storm study", "closed")
        + kit.section_row(218, SECTION_ICONS[Section.REFERENCE], kit.ui(SECTION_LABELS[Section.REFERENCE]), "closed", cls="dim"))


def table(y, headers, columns):
    return (f'<rect x="{DX + 14}" y="{y}" width="{DW - 28}" height="22" fill="var(--side)"/>'
            + "".join(f'<text x="{DX + 22 + x}" y="{y + 15}" class="small dim">{kit.ui(h)}</text>' for h, x in zip(headers, columns)))


def row(y, cells, columns, cls=""):
    return f'<g class="{cls}">' + "".join(f'<text x="{DX + 22 + x}" y="{y + 15}" class="small">{c}</text>' for c, x in zip(cells, columns)) + "</g>"


def box(x, y, w, text_class="", text=""):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="22" rx="5" fill="var(--win)" stroke="var(--line)"/>'
            + (f'<text x="{x + 8}" y="{y + 15}" class="small {text_class}">{text}</text>' if text else ""))


def button(x, y, w, text):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="22" rx="6" fill="var(--side)" stroke="var(--line)"/>'
            f'<text x="{x + w / 2}" y="{y + 15}" text-anchor="middle" class="small">{kit.ui(text)}</text>')


DIALOG = f"""<g class="dialog a">
<rect x="{DX}" y="{DY + 3}" width="{DW}" height="{DH}" rx="10" fill="var(--shadow)"/>
<rect x="{DX}" y="{DY}" width="{DW}" height="{DH}" rx="10" fill="var(--win)" stroke="var(--line)"/>
<text x="{DX + DW / 2 - 34}" y="{DY + 18}" text-anchor="end" class="title">{kit.ui("Sharing:")}</text>
<text x="{DX + DW / 2 - 30}" y="{DY + 18}" class="title">Storm study</text>
{table(DY + 32, ("Member", "Role"), (0, 220))}
{row(DY + 54, ("me@example.org", "owner"), (0, 220))}
<text x="{DX + 14}" y="{DY + 89}" class="small" style="font-weight:600">{kit.ui("Invite")}</text>
{box(DX + 14, DY + 106 - 11, 236)}
<text x="{DX + 22}" y="{DY + 110}" class="small dim placeholder a">{kit.ui("Email, or leave empty for a link")}</text>
<text x="{DX + 22}" y="{DY + 110}" class="small typed1 a">ada@</text>
<text x="{DX + 22}" y="{DY + 110}" class="small typed2 a">ada@example.org</text>
<rect class="focus a" x="{DX + 14}" y="{DY + 95}" width="236" height="22" rx="5" fill="none" stroke="var(--accent)" stroke-width="2"/>
{kit.combo(DX + 258, 80, kit.ui(VIEWER), y=DY + 95)}
{button(DX + DW - 74, DY + 95, 60, "Invite")}
<g class="sent a">{box(DX + 14, DY + 123, 300, "dim", "https://cocat.example.org/invite/7f3c…")}{button(DX + 322, DY + 123, 84, "Copy link")}</g>
<text x="{DX + 14}" y="{DY + 170}" class="small" style="font-weight:600">{kit.ui("Pending invitations")}</text>
{table(DY + 178, ("Invitation", "Role", "Expires"), (0, 170, 260))}
{row(DY + 200, ("ada@example.org", VIEWER, "2026-12-07"), (0, 170, 260), "sent a")}
{button(DX + 14, DY + DH - 34, 110, "Open in browser")}{button(DX + 132, DY + DH - 34, 70, "Refresh")}{button(DX + DW - 84, DY + DH - 34, 70, "Close")}
</g>"""

BODY = f"""{kit.window(P, active="catalogue")}
{kit.panel_frame(x=252, title_x=258)}
{kit.static_plot(268, 104, 400, {"bx": "c1", "by": "c2", "bz": "c3"})}
{kit.static_plot(268, 214, 400, {"density": "c3"})}
{kit.time_pill(474)}
{kit.pane(kit.ui("Catalogs"), ROWS, hot_y=190, hot_class="")}
{kit.popup(MENU_X, MENU_Y, MENU_W, MENU_ROWS, hot=3, cls="menu a")}
{DIALOG}
{kit.ring("rc", *PROJECT)}{kit.ring("choose", *SHARING)}{kit.ring("field", *FIELD)}{kit.ring("send", *INVITE)}
<g transform="translate({PROJECT[0] + 14} {PROJECT[1] - 58})">{kit.keycap("Right-click", cls="key a")}</g>
{kit.CURSOR}
{kit.step(58, 1, "Right-click a project: Sharing…", "s1")}
{kit.step(300, 2, "Type an email, then Invite", "s2")}
{kit.step(510, 3, "The invitation waits", "s3")}"""

SVG = kit.svg(P, "Right-click a project under Shared in the Catalogs pane and choose Sharing…. Type the person's email, "
              "pick a role and click Invite: the invitation is listed under Pending invitations.", STYLE, BODY)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "share-a-catalog-project.svg").write_text(SVG)
print(len(SVG))
