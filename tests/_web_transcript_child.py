"""Runs the web transcript in a real QWebEngineView and prints what it did.

Driven by test_web_transcript_browser.py in a subprocess: the test suite
itself runs without WebEngine (SCIQLOP_TEST_NO_WEBENGINE=1)."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from PySide6.QtCore import QCoreApplication, Qt

QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

from SciQLop.core.sciqlop_application import sciqlop_app  # noqa: E402

app = sciqlop_app()

from SciQLop.components.agents.chat.view import ChatMessage, TextBlock, ToolActivityBlock  # noqa: E402
from SciQLop.components.agents.chat.web_view import WebTranscriptView  # noqa: E402

remote_hits = []


class _Recorder(BaseHTTPRequestHandler):
    def do_GET(self):
        remote_hits.append(self.path)
        self.send_response(404)
        self.end_headers()

    def log_message(self, *args):
        pass


def pump(seconds):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.02)


def js(view, code):
    out = []
    view._view.page().runJavaScript(code, 0, out.append)
    end = time.time() + 5
    while not out and time.time() < end:
        app.processEvents()
        time.sleep(0.02)
    return out[0] if out else None


def main():
    server = HTTPServer(("127.0.0.1", 0), _Recorder)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    view = WebTranscriptView()
    view.resize(600, 400)
    view.show()
    pump(4)

    text = "\n\n".join(f"Paragraph {i} " + "word " * 30 for i in range(80))
    image = f"![x](http://127.0.0.1:{server.server_port}/leak?q=secret)"
    messages = [ChatMessage(role="assistant", done=True, blocks=[
        ToolActivityBlock(tool_name="t", result="ok"),
        TextBlock(text=image + "\n\n" + text, complete=True)])]
    view.render_messages(messages)
    view.flush_now()
    pump(2)
    group = next(p["id"] for m in json.loads(view._model_json()) for p in m["parts"] if p["type"] == "tools")

    view._on_toggle(group)
    pump(2)
    expanded_after_toggle = group in view._expanded
    view._load_html()  # what a theme change does
    pump(4)
    expanded_after_reload = group in view._expanded

    js(view, "window.scrollTo(0, 400)")
    pump(1)
    view.render_messages(messages + [ChatMessage(role="user", done=True, blocks=[TextBlock(text="more", complete=True)])])
    view.flush_now()
    pump(1)
    js(view, "window.scrollTo(0, 100)")
    pump(1)
    view.resize(250, 380)
    pump(2)

    print(json.dumps({
        "remote_hits": remote_hits,
        "expanded_after_toggle": expanded_after_toggle,
        "expanded_after_reload": expanded_after_reload,
        "scroll_y_after_resize": js(view, "window.scrollY"),
    }), flush=True)


main()
