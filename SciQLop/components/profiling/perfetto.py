"""Open a Chrome-trace JSON in https://ui.perfetto.dev/.

Perfetto is a static SPA that runs entirely client-side — the trace itself
never leaves the user's machine. There are two documented ways to hand it a
trace from outside:

  1. URL method — `?url=https://...` — but Perfetto strictly requires HTTPS
     and rejects http://localhost, which makes it useless for local files.
  2. postMessage method — open https://ui.perfetto.dev via `window.open`,
     do a PING/PONG handshake, then `postMessage({perfetto: {buffer, …}})`.
     This is the documented path for self-hosted / local traces.

We can't postMessage from Python, so we serve a tiny launcher HTML page from
a localhost HTTP server. The page fetches the trace bytes from a sibling
URL on the same origin, does the handshake, and posts the trace.

Refs:
- https://perfetto.dev/docs/visualization/deep-linking-to-perfetto-ui
"""
from __future__ import annotations

import http.server
import json
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Union

from SciQLop.components import sciqlop_logging

log = sciqlop_logging.getLogger(__name__)

_SERVER_LIFETIME_SECONDS = 300


_LAUNCHER_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Open trace in Perfetto</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: system-ui, -apple-system, sans-serif;
         max-width: 40rem; margin: 0 auto; padding: 2rem;
         line-height: 1.5; }}
  h1 {{ font-size: 1.4rem; margin-bottom: 0.2rem; }}
  .meta {{ color: #666; margin-bottom: 1.5rem; font-size: 0.9rem; }}
  button {{ padding: 0.6rem 1.4rem; font-size: 1rem; cursor: pointer;
           border-radius: 4px; border: 1px solid #888; background: #f7f7f7; }}
  button:hover {{ background: #eaeaea; }}
  button:disabled {{ opacity: 0.5; cursor: not-allowed; }}
  #status {{ margin-top: 1rem; min-height: 1.5em; color: #555;
            font-family: monospace; }}
</style>
</head>
<body>
<h1>SciQLop runtime trace</h1>
<div class="meta">
  File: <code>{filename}</code> &nbsp;·&nbsp;
  Size: <span id="size">loading…</span>
</div>
<button id="go" disabled>Open in Perfetto</button>
<div id="status"></div>

<script>
const TRACE_URL = "/trace";
const FILENAME  = {filename_json};
const TARGET    = "https://ui.perfetto.dev";

const $ = (id) => document.getElementById(id);
const setStatus = (s) => $("status").textContent = s;

let buffer = null;
fetch(TRACE_URL)
  .then((r) => {{ if (!r.ok) throw new Error("HTTP " + r.status); return r.arrayBuffer(); }})
  .then((b) => {{
    buffer = b;
    $("size").textContent = (b.byteLength / 1024).toFixed(1) + " KB";
    $("go").disabled = false;
    // Try to auto-open. Many browsers allow window.open for ~5s after the
    // tab itself was opened by the user (transient activation). If blocked,
    // the button is still there.
    setTimeout(openInPerfetto, 200);
  }})
  .catch((e) => setStatus("Failed to load trace: " + e.message));

$("go").addEventListener("click", openInPerfetto);

function openInPerfetto() {{
  if (!buffer) {{ setStatus("Trace not loaded yet."); return; }}
  const win = window.open(TARGET + "/#!/");
  if (!win) {{ setStatus("Pop-up blocked — click the button above to retry."); return; }}
  setStatus("Waiting for Perfetto to wake up…");

  const onMessage = (e) => {{
    if (e.data !== "PONG") return;
    clearInterval(pinger);
    window.removeEventListener("message", onMessage);
    win.postMessage(
      {{ perfetto: {{ buffer: buffer, title: FILENAME, fileName: FILENAME }} }},
      TARGET,
    );
    setStatus("Trace sent. You can close this tab.");
  }};
  window.addEventListener("message", onMessage);

  const pinger = setInterval(() => {{
    try {{ win.postMessage("PING", TARGET); }} catch (e) {{}}
  }}, 50);

  setTimeout(() => {{
    clearInterval(pinger);
    window.removeEventListener("message", onMessage);
    if (!win.closed) setStatus("Trace sent (or Perfetto never replied).");
  }}, 30000);
}}
</script>
</body>
</html>
"""


class _Handler(http.server.BaseHTTPRequestHandler):
    server_version = "SciQLopProfiling/1.0"

    def do_GET(self):  # noqa: N802 — http.server contract
        srv = self.server
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, "text/html; charset=utf-8", srv.launcher_html.encode("utf-8"))
        elif path == "/trace":
            self._send(200, "application/json", srv.trace_bytes,
                       extra={"Access-Control-Allow-Origin": "*"})
        else:
            self.send_error(404)

    def _send(self, status, content_type, body, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args, **kwargs):
        return


def _build_launcher_html(filename: str) -> str:
    return _LAUNCHER_HTML.format(
        filename=filename,
        filename_json=json.dumps(filename),
    )


def open_trace_in_perfetto(path: Union[str, Path]) -> str:
    """Serve `path` from a one-shot localhost server and open Perfetto in the
    user's default browser via the postMessage handshake. Returns the URL
    that was launched (the launcher page).
    """
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise FileNotFoundError(p)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    srv.trace_bytes = p.read_bytes()
    srv.launcher_html = _build_launcher_html(p.name)
    port = srv.server_address[1]

    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def _shutdown_after_lifetime():
        time.sleep(_SERVER_LIFETIME_SECONDS)
        try:
            srv.shutdown()
        except Exception:
            pass

    threading.Thread(target=_shutdown_after_lifetime, daemon=True).start()

    url = f"http://127.0.0.1:{port}/"
    log.info("Opening %s via launcher %s", p, url)
    webbrowser.open(url)
    return url
