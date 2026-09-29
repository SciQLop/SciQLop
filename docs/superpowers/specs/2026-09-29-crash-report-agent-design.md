# Crash → agent-written bug report

Status: implemented 2026-09-29. Revised after an opencode review
(findings verified against the code).

## Goal

After SciQLop crashes, the next start offers to let the user's configured
agent investigate the crash and file a GitHub issue.

The agent reads the raw material (session log, macOS crash report) and
writes a *diagnosis*. The published issue never carries raw stack dumps or
home paths. SciQLop code does no parsing or symbolication — the agent does
the diagnostic work, which also saves maintainer triage time.

## Non-goals (v1)

- Hangs (user kills a frozen app — no crash signal, no report).
- Native minidumps on Windows (needs a WER `LocalDumps` registry key).
- Users without an agent: they get the banner with "Open log" only.

## Process tree (why ownership is where it is)

A native install runs three processes:

1. C++ launcher → spawns `python -I -m SciQLop.app` (`launcher.cpp:279`).
2. Python launcher (`sciqlop_launcher.py`) sees `SCIQLOP_STARTUP_READY_FILE`,
   runs one session via `_run_on_console` → `_spawn_app_logged`.
3. The GUI process.

Consequences:

- The C++ launcher never sees the GUI's signal. The Python launcher gets
  `returncode == -11`, then `sys.exit(-11)` exits with status 245. And the
  C++ launcher does not know the GUI's pid (it is a grandchild).
- **Only the Python launcher knows both the GUI pid and how it died.** It
  exists on every install path (native, pip, dev). It owns the crash marker.

## 1. Dated session logs with rotation

Today there are two writers on `last-launch.log` in native installs — an
existing bug, fixed by this section:

- The C++ launcher truncates it on round 1 and tees the Python launcher's
  output into it in append mode (`launcher.cpp:92`, `:221`).
- The Python launcher then reopens the same file with `"w"`
  (`sciqlop_launcher.py:271`), erasing the C++ header/round marker, and
  writes GUI output at its own offset, overwriting lines the C++ side
  appended. The GUI output also appears twice (Python echoes it to stdout,
  which C++ tees).
- A third truncating write happens on workspace-prep failure
  (`sciqlop_launcher.py:508`).

New contract:

- Location: `<launcher data root>/logs/sciqlop-YYYYMMDD-HHMMSS-<pid>.log`
  (the root is `paths::user_data_dir()` = platformdirs `sciqlop` dir, *not*
  `components.storage.user_data_dir()` which adds `data/`). The pid avoids
  same-second collisions; clock changes only affect rotation order, which is
  harmless.
- Whoever creates the file does `mkdir -p logs`, then deletes the oldest so
  at most 10 remain (lexical sort of names).
- C++ launcher: creates the file once per launcher process, keeps appending
  across restart/switch rounds, exports `SCIQLOP_SESSION_LOG=<path>`.
- Python launcher: if `SCIQLOP_SESSION_LOG` is set, it does **not** write
  the file itself (its stdout/stderr already reach it through the C++ tee);
  it only uses the path for the marker. Otherwise (pip/dev) it creates its
  own dated file with the same naming and rotation, in append mode.
- The workspace-prep failure path appends instead of `write_text`.
- `last-launch.log` goes away. Update `launcher/README.md`, the `paths.hpp`
  header comment, and `tests/test_launcher.py`.

## 2. Python stack always captured

In the GUI process, as early as possible in startup:

```python
faulthandler.enable(file=open(session_log, "a"))  # when SCIQLOP_SESSION_LOG is set
faulthandler.enable()                              # otherwise (stderr)
```

Plain stderr would also work today: `faulthandler` keeps the fd it got at
`enable()` time, and jupyqt only swaps `sys.stderr` at the Python level
during cell execution (it does not use ipykernel's fd-level capture). The
explicit file is chosen so the dump does not depend on two relay processes
(Python launcher drain thread → C++ tee) staying alive and draining, nor on
some plugin later `dup2`-ing fd 2. `O_APPEND` keeps whole writes safe next
to the launchers' writers.

- Python 3.14 defaults to `c_stack=True`: native frames are dumped too. Keep
  it — on Linux/Windows it is the only native stack we get.
- This does not conflict with `hang_dump`, which only uses
  `faulthandler.register(SIGUSR1)`.
- Alternative considered: `-X faulthandler` on the C++ launcher's argv. It
  only reaches the Python launcher, not the GUI, and cannot pick the file.
- On macOS the `.ips` has native frames only; this adds which Python slot or
  plugin was running.

## 3. Crash marker (Python launcher)

After `proc.wait()` in `_spawn_app_logged`'s caller, write
`<launcher data root>/crash-pending.json` **only on abnormal termination**:

- POSIX: `returncode < 0` (killed by a signal).
- Windows: `returncode >= 0xC0000000` (NTSTATUS exception, e.g. access
  violation `0xC0000005`).

Handled exits are not crashes: the app's own `exit(1)` on a startup error
(`sciqlop_app.py:199`), 64, 65, and the launcher's restart-budget exit.

```json
{"time": "2026-09-29T17:19:03+02:00", "pid": 12345, "platform": "macos",
 "signal": 11, "ntstatus": null, "log": "<session log path>",
 "sciqlop_version": "0.13.1"}
```

`signal` is null on Windows, `ntstatus` is null on POSIX. `pid` is the GUI
process — the one in the macOS `.ips`.

Only the latest crash is kept: a second crash before the banner overwrites
the first. That is fine — the log path still points at the right file, and
older logs stay in `logs/`.

## 4. Offer at next startup

At startup the app reads and **immediately deletes** the marker (content
kept in memory). If `marker["log"]` no longer exists (rotated away), drop it
silently. Otherwise show a non-blocking banner:

> SciQLop closed unexpectedly last time. [Investigate and report] [Open log] [Dismiss]

- "Investigate and report" appears only when at least one agent backend is
  available (`registry.available_backends()` non-empty).
- Its tooltip/confirm text says the log content will be sent to the
  configured model provider.
- Crash loops at startup never reach the banner; the launcher's error dialog
  still covers that case.

## 5. Agent session

New API: `chat_dock.draft_agent_conversation(main_window, prompt, backend)`
reveals the agent panel, switches to the chosen agent, resets to a fresh
session and puts the prompt in the input box **unsent**: the user picks the
model, may edit it, and sends it. With several agents installed,
"Investigate and report" opens a menu of them, the current one first.

The launcher error window has a "Restart SciQLop" button (launcher 0.2.1):
after a crash it starts a new round, and that start shows the offer.

The agent reads the crash through a SciQLop tool rather than its own file
tools: `sciqlop_read_crash_report` (ungated) returns the marker, the
versions, the last 300 lines of the session log, and on macOS the crashed
thread of the `.ips` whose JSON `pid` matches (exception, termination, up
to 40 frames with image names), all scrubbed. This works in every write
mode, including "writes disabled", and needs no permission for
`~/Library/Logs` — so the session is *not* forced into CONFIRM mode.

The prompt is `components/crash_report/resources/investigate_crash.md`. It
asks the agent to:

1. Call `sciqlop_read_crash_report`.
2. Identify the crashing component (SciQLop, SciQLopPlots, a plugin, Qt)
   and the likely trigger, with a confidence.
3. Search the GitHub issues for an existing report. A duplicate gets a link
   and a suggested comment, not a new issue.
4. Draft a short issue: summary, suspected cause, steps to reproduce if
   inferable, versions. A few key frames at most, no home paths, no
   data/product names that were not needed.
5. Show the draft, and only after the user agrees call
   `sciqlop_open_bug_report`.

## 6. Publishing

`sciqlop_open_bug_report(title, body)` (ungated) scrubs both — home
directory to `~`, user name to `<user>` — and opens
`https://github.com/SciQLop/SciQLop/issues/new?title=…&body=…` in the
browser, with the body capped at 6000 characters. The user submits it there;
that page is the final confirmation.

→ skipped: `gh issue create`. The prefilled page needs no GitHub login and
cannot post behind the user's back; add `gh` if users ask for one-click
posting.

## Testing

`faulthandler._sigsegv()` crashes a process on demand on all three OSes.
Chain tests must drive the real `sciqlop_launcher.py` (the launcher smoke
test uses stub scripts, `launcher/tests/smoke_test.sh`):

- rotation: 11 sessions → 10 logs, newest kept, `logs/` created if missing;
- native mode: Python launcher does not write the log when
  `SCIQLOP_SESSION_LOG` is set (no duplicate lines, header survives);
- crash → marker with GUI pid, signal/ntstatus, log path; faulthandler stack
  in the log;
- exit 0/1/64/65 → no marker;
- banner: shown once, marker deleted on read, dropped if the log is gone;
- macOS runner: an `.ips` whose parsed `pid` matches appears in
  `DiagnosticReports` (validates the agent's lookup; the agent itself is not
  tested).

## Adjacent fix

`hang_dump.install_signal_dump()` calls `faulthandler.register(SIGUSR1)`,
which does not exist on Windows; with `SCIQLOP_DEBUG` set it raises there.
One-line platform guard, separate commit.

## Cost

About 2–2.5 days: logs + rotation + env plumbing ¾, marker ¼,
faulthandler ¼, banner ½, dock entry point + CONFIRM override + template ½,
scrub + publish ¼. Then a manual run on a real Mac.
