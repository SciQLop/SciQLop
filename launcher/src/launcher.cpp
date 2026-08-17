#include "launcher.hpp"

#include "manifest.hpp"
#include "paths.hpp"
#include "process.hpp"
#include "project.hpp"

#include <deque>
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

/// Interpreter series used when a workspace does not pin one. Only ever applied
/// to *new* workspaces; an existing one keeps whatever it recorded.
constexpr const char* DEFAULT_PYTHON_VERSION = "3.14";
constexpr const char* SWITCH_TARGET_FILE = ".sciqlop_switch_target";
constexpr const char* READY_FILE_ENV = "SCIQLOP_STARTUP_READY_FILE";

#ifdef _WIN32
constexpr const char* UV_EXECUTABLE = "uv.exe";
constexpr const char* VENV_PYTHON = ".venv/Scripts/python.exe";
#else
constexpr const char* UV_EXECUTABLE = "uv";
constexpr const char* VENV_PYTHON = ".venv/bin/python";
#endif

/// Bundled uv sits beside the launcher; falling back to PATH keeps development
/// checkouts working without a bundle layout.
std::string uv_command() {
    std::error_code ec;
    for (const fs::path& candidate : {paths::executable_dir() / UV_EXECUTABLE,
                                      paths::executable_dir() / "uv" / UV_EXECUTABLE}) {
        if (fs::is_regular_file(candidate, ec)) return candidate.string();
    }
    return UV_EXECUTABLE;
}

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

/// Bounded tail of a command's output, so a failure message can quote the part
/// that matters without holding a whole `uv sync` transcript in memory.
class LineTail {
public:
    void push(const std::string& line) {
        lines_.push_back(line);
        if (lines_.size() > CAPACITY) lines_.pop_front();
    }

    std::string text() const {
        std::ostringstream out;
        for (const auto& line : lines_) out << line << '\n';
        return out.str();
    }

private:
    static constexpr size_t CAPACITY = 40;
    std::deque<std::string> lines_;
};

/// One log per launch, appended to by every subprocess of that session, so the
/// path quoted in an error message always holds the failure that caused it.
void start_session_log(const fs::path& workspace_dir) {
    std::ofstream log(paths::last_launch_log(), std::ios::binary | std::ios::trunc);
    log << "SciQLop launcher " << SCIQLOP_LAUNCHER_VERSION << '\n'
        << "workspace: " << workspace_dir.string() << "\n\n";
}

void log_line(const char* label, const std::string& line) {
    std::ofstream log(paths::last_launch_log(), std::ios::binary | std::ios::app);
    log << '[' << label << "] " << line << '\n';
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

/// Everything uv prints goes three places: the splash detail line (progress),
/// the session log (post-mortem), and a bounded tail (the error box). Losing
/// any one of them is how a failed sync turns into an unexplained empty venv.
int run_uv(const Command& command, Ui& ui, LineTail& tail) {
    return run(command, [&](const std::string& line) {
        ui.post_detail(line);
        log_line("uv", line);
        tail.push(line);
    });
}

int sync_workspace(const fs::path& workspace_dir, const Manifest& manifest, Ui& ui,
                   LineTail& tail) {
    const std::string python_version =
        manifest.python_version.empty() ? DEFAULT_PYTHON_VERSION : manifest.python_version;

    ui.post_phase("Preparing workspace");
    ui.post_progress(10);

    std::error_code ec;
    if (!fs::is_regular_file(workspace_dir / VENV_PYTHON, ec)) {
        ui.post_detail("Creating environment (Python " + python_version + ")");
        const Command create{{uv_command(), "venv", "--python", python_version, ".venv"},
                             workspace_dir,
                             {}};
        if (const int code = run_uv(create, ui, tail); code != 0) return code;
    }

    ui.post_progress(35);
    ui.post_detail("Resolving dependencies");
    const Command sync{{uv_command(), "sync"}, workspace_dir, {}};
    return run_uv(sync, ui, tail);
}

int supervise_app(const fs::path& workspace_dir, Ui& ui, std::string& stderr_tail) {
    const ReadyFile ready(workspace_dir);

    ui.post_phase("Starting SciQLop");
    ui.post_detail("");
    ui.post_progress(90);

    const Command app{
        {(workspace_dir / VENV_PYTHON).string(), "-m", "SciQLop.sciqlop_app"},
        workspace_dir,
        {{"SCIQLOP_WORKSPACE_DIR", workspace_dir.string()},
         {"SPEASY_SKIP_INIT_PROVIDERS", "1"},
         {"PYTHONNOUSERSITE", "1"},
         {READY_FILE_ENV, ready.marker.string()}}};

    bool splash_closed = false;
    std::ostringstream tail;

    const int code = run_supervised(
        app, paths::last_launch_log(),
        [&tail](const std::string& line) { tail << line << '\n'; },
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

        Manifest manifest = read_manifest(workspace_dir)
                                .value_or(Manifest{workspace_dir.filename().string(), "", ""});
        if (!options.sciqlop_version.empty()) manifest.sciqlop_version = options.sciqlop_version;
        if (!fs::is_regular_file(workspace_dir / Manifest::filename, ec))
            write_manifest(workspace_dir, manifest);

        write_pyproject_if_missing(
            workspace_dir,
            {manifest.name, manifest.sciqlop_version,
             manifest.python_version.empty() ? DEFAULT_PYTHON_VERSION : manifest.python_version});

        LineTail uv_output;
        if (const int code = sync_workspace(workspace_dir, manifest, ui, uv_output); code != 0) {
            ui.post_error("Workspace preparation failed \xe2\x80\x94 uv exited with " +
                          std::to_string(code) + ".\n\n" + uv_output.text() +
                          "\nFull output: " + paths::last_launch_log().string());
            result.exit_code = 1;
            return;
        }

        std::string stderr_tail;
        result.exit_code = supervise_app(workspace_dir, ui, stderr_tail);
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
