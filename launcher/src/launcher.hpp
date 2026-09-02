// Application supervision.
//
// Workspace resolution belongs to Python (sciqlop_launcher.py's
// resolve_workspace_dir(), called from its own main()); the launcher only
// forwards passthrough arguments and drives the restart (64) / workspace
// switch (65) round loop. Everything here is toolkit-independent: it talks to
// the UI only through the Ui interface, so the FLTK front end can be swapped
// without touching it.
#pragma once

#include "ui.hpp"

#include <filesystem>
#include <optional>
#include <string>
#include <vector>

namespace sciqlop {

/// Exit codes the application uses to ask the launcher for another round.
inline constexpr int EXIT_RESTART = 64;
inline constexpr int EXIT_SWITCH_WORKSPACE = 65;

/// Why the current round is running — drives both the splash's initial phase
/// text and the session log's round marker for round >= 2.
enum class RoundKind { Start, Restart, Switch };

struct Options {
    std::string workspace;                 ///< from --workspace/-w; empty => let Python resolve
    std::string sciqlop_file;              ///< positional .sciqlop/.sciqlop-archive file
    std::vector<std::string> passthrough;  ///< every other argument, in argv order
};

/// *args* is argv[1..] (no program name) — see main.cpp for how each platform
/// produces it.
Options parse_args(const std::vector<std::string>& args);

/// The argv this round hands to python3 -I -m SciQLop.app: passthrough, then
/// --workspace <workspace> if set, then the positional file if set. Exposed
/// so command building is unit-testable without spawning a process.
std::vector<std::string> app_argv(const Options& options);

/// Classify one line of the supervised app's STDOUT as a phase transition.
/// Matches the two exact lines sciqlop_launcher.py's _run_on_console() prints
/// for every launch it runs (one session per round now — see run_session).
/// STDERR is never classified this way — a crash traceback must not look like
/// progress.
std::optional<std::string> phase_for_line(const std::string& line);

/// Read, trim and delete *handoff_file* — the workspace-switch target
/// sciqlop_launcher.py's native-mode path leaves behind. Returns "" if the
/// file is missing or blank; the file is removed in either case it exists.
std::string take_switch_target(const std::filesystem::path& handoff_file);

struct SessionResult {
    int exit_code = 0;
    /// Meaningful only when exit_code == EXIT_SWITCH_WORKSPACE: the next
    /// workspace to run, already read from the handoff file. Empty means no
    /// target was found — the caller must stop the round loop.
    std::string switch_target;
};

/// Run one round to completion, driving *ui*. *round* is 1 for the very first
/// round of this launcher process; *kind* says why this round is running.
SessionResult run_session(const Options& options, Ui& ui, int round, RoundKind kind);

/// Warning text when libxcb-cursor is missing on Linux, empty otherwise.
std::string xcb_cursor_warning();

}  // namespace sciqlop
