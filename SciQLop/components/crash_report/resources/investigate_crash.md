SciQLop closed unexpectedly during my last session. Please investigate the crash and help me report it.

1. Call the `sciqlop_read_crash_report` tool. It returns the crash marker (pid, signal), the versions, the end of the session log with the Python stack of every thread, and on macOS the crashed thread from the system crash report.
2. Work out which component crashed (SciQLop, SciQLopPlots, a plugin, Qt/PySide6 or another library) and what most likely triggered it. Say how confident you are.
3. Look for an existing report of the same crash in https://github.com/SciQLop/SciQLop/issues (and https://github.com/SciQLop/SciQLopPlots/issues if it points there). If you cannot browse, say so and skip this step.
4. Draft a short issue: a one-line title, then a summary, the suspected cause, steps to reproduce if you can infer them, and the versions. Quote a few key frames at most. Leave out raw stack dumps, personal paths, user names, and any data or product names the report does not need.
5. Show me the draft. Only once I agree, call `sciqlop_open_bug_report` with the title and body: it opens the prefilled issue in my browser, and I submit it myself. If you found an existing issue instead, give me its link and a suggested comment rather than opening a new one.
