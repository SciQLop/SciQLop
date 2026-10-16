"""A minimal ACP agent over stdio (newline-delimited JSON-RPC), for tests that need the real client SDK on the wire.

Usage: python acp_fake_agent.py STATE_FILE [--deletes] [--commands]
STATE_FILE holds {"sessions": [{"sessionId", "cwd"}...], "created": [cwd...]} so that separate spawns see the same
sessions, and a test can see where deleted sessions were opened.
--deletes advertises sessionCapabilities.delete and serves session/delete.
--commands sends an available_commands_update right after answering session/new, as opencode does.
"""
import json
import sys
from pathlib import Path

state_file = Path(sys.argv[1])
deletes = "--deletes" in sys.argv[2:]
commands = "--commands" in sys.argv[2:]


def _load() -> dict:
    return json.loads(state_file.read_text()) if state_file.exists() else {"sessions": []}


def _save(state: dict) -> None:
    state_file.write_text(json.dumps(state))


def _initialize(_params):
    capabilities = {"sessionCapabilities": {"list": {}, **({"delete": {}} if deletes else {})}}
    return {"protocolVersion": 1, "agentCapabilities": capabilities}


def _new_session(params):
    state = _load()
    session_id = f"s{len(state['sessions']) + 1}"
    state["sessions"].append({"sessionId": session_id, "cwd": params["cwd"]})
    state.setdefault("created", []).append(params["cwd"])
    _save(state)
    return {"sessionId": session_id}


def _list_sessions(params):
    return {"sessions": [dict(s, title=s["sessionId"]) for s in _load()["sessions"] if s["cwd"] == params["cwd"]]}


def _delete_session(params):
    state = _load()
    state["sessions"] = [s for s in state["sessions"] if s["sessionId"] != params["sessionId"]]
    _save(state)
    return {}


_METHODS = {"initialize": _initialize, "session/new": _new_session, "session/list": _list_sessions}
if deletes:
    _METHODS["session/delete"] = _delete_session


def _reply(message: dict) -> dict:
    handler = _METHODS.get(message["method"])
    if handler is None:
        return {"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32601, "message": "Method not found"}}
    return {"jsonrpc": "2.0", "id": message["id"], "result": handler(message.get("params") or {})}


def _commands_update(session_id: str) -> dict:
    update = {"sessionUpdate": "available_commands_update",
              "availableCommands": [{"name": "review", "description": "Review"},
                                    {"name": "sciqlop-catalogs", "description": "A skill"}]}
    return {"jsonrpc": "2.0", "method": "session/update", "params": {"sessionId": session_id, "update": update}}


def _send(message: dict) -> None:
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


for line in sys.stdin:
    message = json.loads(line)
    if "id" in message and "method" in message:
        reply = _reply(message)
        _send(reply)
        if commands and message["method"] == "session/new":
            _send(_commands_update(reply["result"]["sessionId"]))
