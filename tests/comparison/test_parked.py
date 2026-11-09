"""The comparison feature is parked for a later release: shipped code, no way in from the app."""


class _RecordingRegistry:
    """Why not CommandRegistry: it writes to the global commands point, re-owning the built-ins as "user"."""

    def __init__(self):
        self.ids = []

    def register(self, command):
        self.ids.append(command.id)


def test_builtin_commands_offer_no_compare(qapp):
    from SciQLop.components.command_palette.commands import register_builtin_commands
    registry = _RecordingRegistry()
    register_builtin_commands(registry)
    assert registry.ids and not [i for i in registry.ids if i.startswith("sciqlop.compare")]


def test_bundled_skills_do_not_teach_compare():
    from pathlib import Path
    import SciQLop.components.agents.skills as skills
    texts = [p.read_text() for p in Path(skills.__file__).parent.rglob("SKILL.md")]
    assert not [t for t in texts if "sciqlop_compare" in t]
