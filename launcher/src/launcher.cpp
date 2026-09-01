#include "launcher.hpp"

#include "manifest.hpp"  // most_recently_used()
#include "paths.hpp"
#include "process.hpp"

#include <fstream>
#include <sstream>

#ifndef SCIQLOP_LAUNCHER_VERSION
#define SCIQLOP_LAUNCHER_VERSION "dev"
#endif

#ifndef _WIN32
#include <dlfcn.h>
#endif

namespace fs = std::filesystem;

namespace sciqlop {
namespace {

constexpr const char* SWITCH_TARGET_FILE = ".sciqlop_switch_target";

/// AppRun (Linux/macOS bundles) and the Windows/macOS installers all put the
/// bundled interpreter's directory on PATH before running this launcher —
/// the same PATH the launcher's own bundled uv is found through today. A dev
/// checkout without that bundling still resolves this to whatever `python3`
/// is on the ambient PATH.
#ifdef _WIN32
constexpr const char* PYTHON_EXECUTABLE = "python.exe";
#else
constexpr const char* PYTHON_EXECUTABLE = "python3";
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

/// Workspaces root, overridable through the launcher-owned config file the app
/// writes when the corresponding setting changes.
fs::path workspaces_root() {
    const std::string config = read_file(paths::launcher_config());
    const auto key = config.find("\"workspaces_dir\"");
    if (key != std::string::npos) {
        const auto open = config.find('"', config.find(':', key) + 1);
        const auto close = config.find('"', open + 1);
        if (open != std::string::npos && close != std::string::npos)
            return fs::path(config.substr(open + 1, close - open - 1));
    }
    return paths::workspaces_root();
}

/// One log per launch, appended to by every subprocess of that session, so the
/// path quoted in an error message always holds the failure that caused it.
void start_session_log(const fs::path& workspace_dir) {
    std::ofstream log(paths::last_launch_log(), std::ios::binary | std::ios::trunc);
    log << "SciQLop launcher " << SCIQLOP_LAUNCHER_VERSION << '\n'
        << "workspace: " << workspace_dir.string() << "\n\n";
}

struct ReadyFile {
    fs::path directory;
    fs::path marker;

    explicit ReadyFile(const fs::path& workspace_dir)
        : directory(workspace_dir / ".sciqlop_startup"), marker(directory / "ready") {
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
/// everything here via `SciQLop.sciqlop_launcher.main()` — resolve the
/// workspace, prepare it (plugin/appstore dependencies, dev-build git-main
/// installs, the offline/plugin-isolation sync retries — see
/// `prepare_workspace()` in the Python codebase), then spawn the real GUI
/// once the workspace venv is ready.
///
/// This launcher's only job is showing a native splash *while* that already
/// correct, already tested Python code runs — reimplementing workspace/venv
/// setup here (as an earlier version of this function did, calling `uv venv`
/// / `uv sync` directly) would just be a second copy to keep in sync, and it
/// had already drifted: no plugin/appstore dependency support, no dev-build
/// git-main install, no retry-on-a-broken-plugin. `--sciqlop-version` isn't
/// forwarded (Python's CLI doesn't parse it yet) — a pre-existing gap, not
/// a regression, since this launcher was never wired into an installer.
///
/// The readiness handoff (`SCIQLOP_STARTUP_READY_FILE`) is the same protocol
/// `sciqlop_app.py`'s `_signal_ready_and_wait_for_splash()` already
/// implements for the windowed Python splash — it just flows through
/// unchanged env-var inheritance down to the actual GUI process, so nothing
/// on the Python side needs to change for this launcher to use it too.
int run_app(const fs::path& workspace_dir, Ui& ui, std::string& stderr_tail) {
    const ReadyFile ready(workspace_dir);

    ui.post_phase("Preparing workspace");
    ui.post_detail("");
    ui.post_progress(10);

    const Command app{
        {PYTHON_EXECUTABLE, "-I", "-m", "SciQLop.app", "--workspace", workspace_dir.string()},
        {},
        {{"SCIQLOP_STARTUP_READY_FILE", ready.marker.string()}}};

    bool splash_closed = false;
    std::ostringstream tail;

    const int code = run_supervised(
        app, paths::last_launch_log(),
        [&](const std::string& line) {
            ui.post_detail(line);
            tail << line << '\n';
        },
        [&] {
            if (splash_closed) return;
            std::error_code ec;
            if (!fs::is_regular_file(ready.marker, ec)) return;
            splash_closed = true;
            ui.post_progress(100);
            ui.post_phase("");  // window is about to close; avoid a stale caption
        });

    stderr_tail = tail.str();
    return code;
}

}  // namespace

Options parse_args(int argc, char** argv) {
    Options options;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        const bool has_next = i + 1 < argc;
        if ((arg == "--workspace" || arg == "-w") && has_next) {
            options.workspace = argv[++i];
        } else if (arg == "--sciqlop-version" && has_next) {
            options.sciqlop_version = argv[++i];
        } else if (!arg.empty() && arg.front() != '-') {
            options.sciqlop_file = arg;
        }
    }
    return options;
}

fs::path resolve_workspace_dir(const Options& options) {
    const fs::path root = workspaces_root();

    if (!options.sciqlop_file.empty()) {
        const fs::path file(options.sciqlop_file);
        if (file.extension() == ".sciqlop") return file.parent_path();
    }
    if (!options.workspace.empty()) {
        const fs::path candidate(options.workspace);
        return candidate.is_absolute() ? candidate : root / options.workspace;
    }
    if (auto recent = most_recently_used(root)) return *recent;
    return root / "default";
}

SessionResult run_session(const Options& options, Ui& ui) {
    SessionResult result;
    result.workspace_dir = resolve_workspace_dir(options);

    ui.run_with_worker([&] {
        const fs::path workspace_dir = result.workspace_dir;
        std::error_code ec;
        fs::create_directories(workspace_dir, ec);
        fs::create_directories(paths::user_data_dir(), ec);
        start_session_log(workspace_dir);

        if (const std::string warning = xcb_cursor_warning(); !warning.empty())
            ui.post_warning(warning);

        std::string stderr_tail;
        result.exit_code = run_app(workspace_dir, ui, stderr_tail);
        if (result.exit_code != 0 && result.exit_code != EXIT_RESTART &&
            result.exit_code != EXIT_SWITCH_WORKSPACE) {
            ui.post_error("SciQLop exited with code " + std::to_string(result.exit_code) +
                          ".\n\nFull output: " + paths::last_launch_log().string() + "\n\n" +
                          stderr_tail);
        }
    });

    return result;
}

std::string take_switch_target(const fs::path& workspace_dir) {
    const fs::path file = workspace_dir / SWITCH_TARGET_FILE;
    std::error_code ec;
    if (!fs::is_regular_file(file, ec)) return {};
    const std::string target = trim(read_file(file));
    fs::remove(file, ec);
    return target;
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
