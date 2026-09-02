#include "launcher.hpp"

#include "paths.hpp"
#include "process.hpp"

#include <fstream>
#include <sstream>
#include <string_view>

#ifndef SCIQLOP_LAUNCHER_VERSION
#define SCIQLOP_LAUNCHER_VERSION "dev"
#endif

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <dlfcn.h>
#include <unistd.h>
#endif

namespace fs = std::filesystem;

namespace sciqlop {
namespace {

/// AppRun (Linux/macOS bundles) and the Windows/macOS installers all put the
/// bundled interpreter's directory on PATH before running this launcher — the
/// same PATH a dev checkout without that bundling resolves to whatever
/// `python3` is on the ambient PATH.
#ifdef _WIN32
constexpr const char* PYTHON_EXECUTABLE = "python.exe";
#else
constexpr const char* PYTHON_EXECUTABLE = "python3";
#endif

/// Env vars sciqlop_launcher.py reads to detect native-launcher mode
/// (READY_FILE_ENV) and to learn where to write a workspace-switch target
/// (SWITCH_HANDOFF_ENV) — see _choose_run_session()/_switch_handoff_path()
/// there. Both must be set together: native mode is only ever entered
/// because READY_FILE_ENV is present, and Python treats a missing
/// SWITCH_HANDOFF_ENV in that mode as a hard error rather than guessing a
/// path.
constexpr const char* READY_FILE_ENV = "SCIQLOP_STARTUP_READY_FILE";
constexpr const char* SWITCH_HANDOFF_ENV = "SCIQLOP_SWITCH_HANDOFF_FILE";

/// A path's bytes as UTF-8, independent of the platform's native/ANSI
/// encoding — the only form that survives unchanged through Command's argv
/// and extra_env into process_win32.cpp's UTF-8-decoding widen().
std::string to_utf8(const fs::path& path) {
    const auto encoded = path.u8string();
    return std::string(encoded.begin(), encoded.end());
}

#ifdef _WIN32
unsigned long current_pid() { return GetCurrentProcessId(); }
#else
long current_pid() { return static_cast<long>(getpid()); }
#endif

std::string read_file(const fs::path& path) {
    std::ifstream in(path, std::ios::binary);
    std::ostringstream out;
    out << in.rdbuf();
    return out.str();
}

std::string trim(std::string value) {
    const auto first = value.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return {};
    const auto last = value.find_last_not_of(" \t\r\n");
    return value.substr(first, last - first + 1);
}

std::string round_kind_name(RoundKind kind) {
    switch (kind) {
        case RoundKind::Restart: return "restart";
        case RoundKind::Switch: return "switch";
        case RoundKind::Start: return "start";
    }
    return "start";
}

/// One log per launcher process: truncated only for round 1, then appended to
/// by every subprocess and every later round — a restart/switch round must
/// never erase the previous round's failure output, since the error window
/// points at this file.
void prepare_round_log(int round, RoundKind kind) {
    if (round == 1) {
        std::ofstream fresh(paths::last_launch_log(), std::ios::binary | std::ios::trunc);
        fresh << "SciQLop launcher " << SCIQLOP_LAUNCHER_VERSION << "\n\n";
    }
    std::ofstream log(paths::last_launch_log(), std::ios::binary | std::ios::app);
    log << "=== round " << round << " (" << round_kind_name(kind) << ") ===\n";
}

/// The startup-ready handshake file and the workspace-switch handoff file,
/// both in the same per-process temp directory — not the workspace dir
/// (which the launcher no longer resolves) and not a fixed user_data_dir
/// path either: a global path for the handoff file would be stale if a
/// launcher died after Python wrote it but before this round read it, or
/// shared between two concurrent launcher instances switching workspace at
/// the same time. Per-pid, like the ready marker, sidesteps both.
struct RoundScratchFiles {
    fs::path directory;
    fs::path ready_marker;
    fs::path switch_handoff;

    RoundScratchFiles()
        : directory(fs::temp_directory_path() /
                    ("sciqlop-launcher-" + std::to_string(current_pid()))),
          ready_marker(directory / "ready"),
          switch_handoff(directory / "next-workspace") {
        std::error_code ec;
        fs::create_directories(directory, ec);
        fs::remove(ready_marker, ec);
        fs::remove(switch_handoff, ec);
    }

    ~RoundScratchFiles() {
        std::error_code ec;
        fs::remove_all(directory, ec);
    }
};

/// Runs ONE session of the bundled thin `sciqlop` launcher package (no [all]
/// extra — the same binary `build.sh` installs, importable without PySide6)
/// via `SciQLop.sciqlop_launcher.main()` — parse argv, resolve the workspace,
/// prepare it (plugin/appstore dependencies, dev-build git-main installs, the
/// offline/plugin-isolation sync retries — see `prepare_workspace()` in the
/// Python codebase), then spawn the real GUI once the workspace venv is
/// ready. Python's own `READY_FILE_ENV` presence is what makes it run exactly
/// one round and return 64/65 instead of looping — see
/// `_choose_run_session()`/`main()` in sciqlop_launcher.py; the round loop
/// itself now lives in run_session/main.cpp.
///
/// This launcher's only job is showing a native splash *while* that already
/// correct, already tested Python code runs, and forwarding argv — reimplementing
/// workspace resolution or venv setup here (as an earlier version of this
/// function did) would just be a second copy of that logic to keep in sync.
///
/// The readiness handoff (`SCIQLOP_STARTUP_READY_FILE`) is the same protocol
/// `sciqlop_app.py`'s `_signal_ready_and_wait_for_splash()` already
/// implements for the windowed Python splash — it just flows through
/// unchanged env-var inheritance down to the actual GUI process, so nothing
/// on the Python side needs to change for this launcher to use it too.
int run_app(const Options& options, Ui& ui, int round, RoundKind kind,
           std::string& stderr_tail, std::string& switch_target) {
    const RoundScratchFiles scratch;

    // Round 1 starts from a blank window, so Python's own "Preparing
    // workspace ..." phase line (via phase_for_line below) is the first thing
    // the user sees. A restart/switch round reuses the same splash contract,
    // but that first Python line can be seconds away (workspace resolution,
    // venv checks) — say what is happening before it arrives.
    if (round == 1) {
        ui.post_phase("Preparing workspace");
    } else {
        ui.post_phase(kind == RoundKind::Switch ? "Switching workspace" : "Restarting SciQLop");
    }
    ui.post_detail("");
    ui.post_progress(10);

    std::vector<std::string> argv{PYTHON_EXECUTABLE, "-I", "-m", "SciQLop.app"};
    const auto forwarded = app_argv(options);
    argv.insert(argv.end(), forwarded.begin(), forwarded.end());

    const Command app{argv,
                      {},
                      {{READY_FILE_ENV, to_utf8(scratch.ready_marker)},
                       {SWITCH_HANDOFF_ENV, to_utf8(scratch.switch_handoff)}}};

    std::ostringstream tail;

    // sciqlop_launcher.py's _run_on_console() prints these two exact lines
    // for every session. Recognizing them turns the splash from a static
    // "Preparing workspace"/"Restarting SciQLop" into a live reflection of
    // what this round is actually doing right now.
    auto report_stdout = [&](const std::string& line) {
        if (const auto phase = phase_for_line(line)) {
            ui.post_phase(*phase);
        } else {
            ui.post_detail(line);
        }
    };

    // stderr never carries a phase marker — only warnings and, on a crash, a
    // traceback — so it always goes to the detail line and, kept verbatim, to
    // post_error()'s tail.
    auto report_stderr = [&](const std::string& line) {
        ui.post_detail(line);
        tail << line << '\n';
    };

    const int code = run_supervised(
        app, paths::last_launch_log(), report_stdout, report_stderr,
        [&] {
            std::error_code ec;
            if (!fs::is_regular_file(scratch.ready_marker, ec)) return;
            // sciqlop_app.py's _signal_ready_and_wait_for_splash() touches this
            // marker, then polls (up to 5s) for it to be *deleted* before
            // showing its own window — the same handoff the windowed Python
            // splash's check_ready() already implements. dismiss() alone hides
            // ours immediately; without also removing the marker, the app
            // would sit at its self-imposed timeout instead of being
            // acknowledged right away.
            ui.dismiss();
            fs::remove(scratch.ready_marker, ec);
        });

    // Read the handoff file (if any) while `scratch` is still alive — its
    // destructor removes the whole per-pid directory, so this must not be
    // deferred to the caller after run_app() returns.
    if (code == EXIT_SWITCH_WORKSPACE) switch_target = take_switch_target(scratch.switch_handoff);

    stderr_tail = tail.str();
    return code;
}

}  // namespace

Options parse_args(const std::vector<std::string>& args) {
    Options options;
    for (size_t i = 0; i < args.size(); ++i) {
        const std::string& arg = args[i];
        const bool has_next = i + 1 < args.size();
        if ((arg == "--workspace" || arg == "-w") && has_next) {
            options.workspace = args[++i];
        } else if (arg == "--sciqlop-version" && has_next) {
            // The one other flag the app's CLI grammar takes a value for —
            // forwarded as-is, so it need not be re-parsed on every round.
            options.passthrough.push_back(arg);
            options.passthrough.push_back(args[++i]);
        } else if (!arg.empty() && arg.front() != '-') {
            options.sciqlop_file = arg;
        } else {
            options.passthrough.push_back(arg);
        }
    }
    return options;
}

std::vector<std::string> app_argv(const Options& options) {
    std::vector<std::string> argv = options.passthrough;
    if (!options.workspace.empty()) {
        argv.push_back("--workspace");
        argv.push_back(options.workspace);
    }
    if (!options.sciqlop_file.empty()) argv.push_back(options.sciqlop_file);
    return argv;
}

std::optional<std::string> phase_for_line(const std::string& line) {
    if (line == "Starting SciQLop ...") return "Starting SciQLop";

    constexpr std::string_view prefix = "Preparing workspace ";
    constexpr std::string_view suffix = " ...";
    const std::string_view view = line;
    if (view.size() < prefix.size() + suffix.size()) return std::nullopt;
    if (view.substr(0, prefix.size()) != prefix) return std::nullopt;
    if (view.substr(view.size() - suffix.size()) != suffix) return std::nullopt;
    return "Preparing workspace";
}

std::string take_switch_target(const fs::path& handoff_file) {
    std::error_code ec;
    if (!fs::is_regular_file(handoff_file, ec)) return {};
    const std::string target = trim(read_file(handoff_file));
    fs::remove(handoff_file, ec);
    return target;
}

SessionResult run_session(const Options& options, Ui& ui, int round, RoundKind kind) {
    SessionResult result;

    ui.run_with_worker([&] {
        std::error_code ec;
        fs::create_directories(paths::user_data_dir(), ec);
        prepare_round_log(round, kind);

        if (const std::string warning = xcb_cursor_warning(); !warning.empty())
            ui.post_warning(warning);

        std::string stderr_tail;
        result.exit_code = run_app(options, ui, round, kind, stderr_tail, result.switch_target);

        if (result.exit_code == EXIT_SWITCH_WORKSPACE) {
            // Must happen here, not after run_with_worker returns: by then
            // this round's window has already closed (see Ui::run_with_worker's
            // contract), so an error posted afterward would never be seen.
            if (result.switch_target.empty()) {
                ui.post_error("SciQLop asked to switch workspace but named no target.");
            }
        } else if (result.exit_code != 0 && result.exit_code != EXIT_RESTART) {
            ui.post_error("SciQLop exited with code " + std::to_string(result.exit_code) +
                          ".\n\nFull output: " + paths::last_launch_log().string() + "\n\n" +
                          stderr_tail);
        }
    });

    return result;
}

std::string xcb_cursor_warning() {
#if defined(__linux__)
    if (void* handle = dlopen("libxcb-cursor.so.0", RTLD_LAZY); handle != nullptr) {
        dlclose(handle);
        return {};
    }
    return "libxcb-cursor0 is not installed \xe2\x80\x94 cursor rendering may be broken.\n"
           "Install it with:  sudo dnf install xcb-util-cursor  (or apt install libxcb-cursor0)";
#else
    return {};
#endif
}

}  // namespace sciqlop
