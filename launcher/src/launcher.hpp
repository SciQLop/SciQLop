// Application supervision.
//
// Workspace resolution belongs to Python (sciqlop_launcher.py's
// resolve_workspace_dir(), called from its own main()): the launcher forwards
// its argv untouched and lets that one already-tested resolution live in one
// place. Everything here is toolkit-independent: it talks to the UI only
// through the Ui interface, so the FLTK front end can be swapped without
// touching it.
#pragma once

#include "ui.hpp"

#include <optional>
#include <string>
#include <vector>

namespace sciqlop {

struct Options {
    std::vector<std::string> forwarded_args;  ///< the launcher's own argv[1..], untouched
};

/// *args* is argv[1..] (no program name) — see main.cpp for how each platform
/// produces it.
Options parse_args(const std::vector<std::string>& args);

/// Classify one line of the supervised app's STDOUT as a phase transition.
/// Matches the two exact lines sciqlop_launcher.py's _run_on_console() prints
/// for every launch, restart or workspace switch it handles internally.
/// STDERR is never classified this way — a crash traceback must not look like
/// progress.
std::optional<std::string> phase_for_line(const std::string& line);

/// Run the application to completion, driving *ui*. Python's own main() loops
/// internally on exit codes 64 (restart) and 65 (switch workspace), so this
/// returns only the final code the session ends with.
int run_session(const Options& options, Ui& ui);

/// Warning text when libxcb-cursor is missing on Linux, empty otherwise.
std::string xcb_cursor_warning();

}  // namespace sciqlop
