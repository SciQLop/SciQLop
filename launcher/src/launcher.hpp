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

#include <chrono>
#include <filesystem>
#include <optional>
#include <string>
#include <vector>

namespace sciqlop {

/// Exit codes the application uses to ask the launcher for another round.
inline constexpr int EXIT_RESTART = 64;
inline constexpr int EXIT_SWITCH_WORKSPACE = 65;

using Clock = std::chrono::steady_clock;

/// How many restart rounds (exit 64) are tolerated inside RESTART_WINDOW
/// before main.cpp gives up instead of spinning forever — a real crash loop
/// looks exactly like a restart round from here, so this is the only signal
/// available to tell the two apart. Switch rounds (65) never count.
inline constexpr int RESTART_BUDGET = 3;
inline constexpr std::chrono::seconds RESTART_WINDOW{60};

/// True once more than RESTART_BUDGET restart rounds started within
/// RESTART_WINDOW of *now*. *restarts* holds every restart round's start
/// time seen so far (including, once pushed, the one about to run); entries
/// older than the window are ignored, so a launcher that has been up for
/// hours with the occasional restart is never penalised for its lifetime
/// total.
bool restart_budget_exhausted(const std::vector<Clock::time_point>& restarts, Clock::time_point now);

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

/// The Options for the next round, given the previous round's Options and
/// how it ended. A restart (EXIT_RESTART) replays exactly what was asked
/// for — same workspace, positional file and passthrough args. A workspace
/// switch (EXIT_SWITCH_WORKSPACE) moves to *switch_target* and drops the
/// positional file, which named a location in the old workspace. Any other
/// exit code returns *options* unchanged.
Options options_for_next_round(Options options, int exit_code, const std::string& switch_target);

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
