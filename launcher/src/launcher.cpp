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

/// One log per launch, appended to by every subprocess of that session, so the
/// path quoted in an error message always holds the failure that caused it.
void start_session_log() {
    std::ofstream log(paths::last_launch_log(), std::ios::binary | std::ios::trunc);
    log << "SciQLop launcher " << SCIQLOP_LAUNCHER_VERSION << "\n\n";
}

/// The startup-ready handshake file, in its own per-process temp directory —
/// not the workspace dir, which the launcher no longer resolves and which two
/// concurrent instances would otherwise share.
struct ReadyFile {
    fs::path directory;
    fs::path marker;

    ReadyFile()
        : directory(fs::temp_directory_path() /
                    ("sciqlop-launcher-" + std::to_string(current_pid()))),
          marker(directory / "ready") {
        std::error_code ec;
        fs::create_directories(directory, ec);
        fs::remove(marker, ec);
    }

    ~ReadyFile() {
        std::error_code ec;
        fs::remove_all(directory, ec);
    }
};

/// Runs the whole workspace-prepare-and-supervise sequence in ONE subprocess:
/// the bundled thin `sciqlop` launcher package (no [all] extra — the same
/// binary `build.sh` installs, importable without PySide6) already does
/// everything here via `SciQLop.sciqlop_launcher.main()` — parse argv,
/// resolve the workspace, prepare it (plugin/appstore dependencies, dev-build
/// git-main installs, the offline/plugin-isolation sync retries — see
/// `prepare_workspace()` in the Python codebase), then spawn the real GUI
/// once the workspace venv is ready, looping internally on exit 64
/// (restart)/65 (switch workspace).
///
/// This launcher's only job is showing a native splash *while* that already
/// correct, already tested Python code runs, and forwarding its own argv
/// untouched — reimplementing workspace resolution or venv setup here (as an
/// earlier version of this function did) would just be a second copy of that
/// logic to keep in sync.
///
/// The readiness handoff (`SCIQLOP_STARTUP_READY_FILE`) is the same protocol
/// `sciqlop_app.py`'s `_signal_ready_and_wait_for_splash()` already
/// implements for the windowed Python splash — it just flows through
/// unchanged env-var inheritance down to the actual GUI process, so nothing
/// on the Python side needs to change for this launcher to use it too.
int run_app(const std::vector<std::string>& forwarded_args, Ui& ui, std::string& stderr_tail) {
    const ReadyFile ready;

    ui.post_phase("Preparing workspace");
    ui.post_detail("");
    ui.post_progress(10);

    std::vector<std::string> argv{PYTHON_EXECUTABLE, "-I", "-m", "SciQLop.app"};
    argv.insert(argv.end(), forwarded_args.begin(), forwarded_args.end());

    const Command app{argv, {}, {{"SCIQLOP_STARTUP_READY_FILE", to_utf8(ready.marker)}}};

    std::ostringstream tail;

    // sciqlop_launcher.py's _run_on_console() prints these two exact lines —
    // once for the very first launch, and again for every restart or
    // workspace switch it handles internally within this one subprocess (see
    // its main() loop). Recognizing them turns the splash from a static
    // "Preparing workspace" for the whole session into a live reflection of
    // which of those internal relaunches is happening right now.
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
            if (!fs::is_regular_file(ready.marker, ec)) return;
            // sciqlop_app.py's _signal_ready_and_wait_for_splash() touches this
            // marker, then polls (up to 5s) for it to be *deleted* before
            // showing its own window — the same handoff the windowed Python
            // splash's check_ready() already implements. dismiss() alone hides
            // ours immediately; without also removing the marker, the app
            // would sit at its self-imposed timeout on every single launch
            // instead of being acknowledged right away.
            //
            // No "already dismissed" latch: the middle `SciQLop.app` process
            // handles a restart (exit 64) or workspace switch (exit 65)
            // *internally*, re-touching this same marker for every GUI
            // relaunch within this one native-launcher session — not just the
            // first. dismiss() is safe to call repeatedly (see ui.hpp), so
            // acknowledging every occurrence is what keeps a restart/switch
            // from sitting at that 5s timeout too.
            ui.dismiss();
            fs::remove(ready.marker, ec);
        });

    stderr_tail = tail.str();
    return code;
}

}  // namespace

Options parse_args(const std::vector<std::string>& args) { return Options{args}; }

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

int run_session(const Options& options, Ui& ui) {
    int exit_code = 0;

    ui.run_with_worker([&] {
        std::error_code ec;
        fs::create_directories(paths::user_data_dir(), ec);
        start_session_log();

        if (const std::string warning = xcb_cursor_warning(); !warning.empty())
            ui.post_warning(warning);

        std::string stderr_tail;
        exit_code = run_app(options.forwarded_args, ui, stderr_tail);
        if (exit_code != 0) {
            ui.post_error("SciQLop exited with code " + std::to_string(exit_code) +
                          ".\n\nFull output: " + paths::last_launch_log().string() + "\n\n" +
                          stderr_tail);
        }
    });

    return exit_code;
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
