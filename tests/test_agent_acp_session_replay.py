"""`replay_to_messages` turns a session/load update stream into ChatMessages
for redisplay after a restart. The live-stream path's tool-call images are
covered by test_agent_acp_stream.py; this covers the replay path, including
a user-attached image (a pasted screenshot) sent as its own content chunk
rather than a tool result.
"""
import pytest

pytestmark = pytest.mark.skipif(
    pytest.importorskip("acp") is None, reason="agent-client-protocol not installed"
)

from SciQLop.components.agents.acp.sessions import replay_to_messages
from SciQLop.components.agents.chat import ImageBlock


def test_user_attached_image_survives_replay(tmp_path):
    from acp import helpers
    updates = [
        helpers.update_user_message_text("here is a screenshot"),
        helpers.update_user_message(helpers.image_block("QUJD", "image/png")),
        helpers.update_agent_message_text("I see it."),
    ]
    messages = replay_to_messages(updates, tmp_path)
    assert len(messages) == 2
    user_msg = messages[0]
    assert user_msg.role == "user"
    images = [b for b in user_msg.blocks if isinstance(b, ImageBlock)]
    assert images, f"expected an ImageBlock in {user_msg.blocks!r}"
    for b in images:
        assert (tmp_path / b.path.split("/")[-1]).exists()
