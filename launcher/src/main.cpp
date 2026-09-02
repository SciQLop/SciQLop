#include "launcher.hpp"
#include "paths.hpp"
#include "ui_fltk.hpp"

#include <filesystem>
#include <string>
#include <vector>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <shellapi.h>
#include <windows.h>
#endif

namespace fs = std::filesystem;

namespace {

/// Splash artwork ships beside the launcher binary.
fs::path splash_path() { return sciqlop::paths::executable_dir() / "splash.png"; }

#ifdef _WIN32
std::string narrow_utf8(const wchar_t* wide) {
    const int size = WideCharToMultiByte(CP_UTF8, 0, wide, -1, nullptr, 0, nullptr, nullptr);
    if (size <= 0) return {};
    std::string out(static_cast<size_t>(size - 1), '\0');
    WideCharToMultiByte(CP_UTF8, 0, wide, -1, out.data(), size, nullptr, nullptr);
    return out;
}

/// The CRT's argv is decoded through the ANSI code page, mangling any
/// character outside it — re-derive argv from the raw UTF-16 command line
/// instead, so a non-ASCII workspace name or path survives.
std::vector<std::string> utf8_argv() {
    int argc = 0;
    LPWSTR* wide_argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    std::vector<std::string> args;
    if (wide_argv != nullptr) {
        for (int i = 1; i < argc; ++i) args.push_back(narrow_utf8(wide_argv[i]));
        LocalFree(wide_argv);
    }
    return args;
}
#else
std::vector<std::string> forwarded_argv(int argc, char** argv) {
    return std::vector<std::string>(argv + 1, argv + argc);
}
#endif

}  // namespace

int main(int argc, char** argv) {
#ifdef _WIN32
    (void)argc;
    (void)argv;
    sciqlop::Options options = sciqlop::parse_args(utf8_argv());
#else
    sciqlop::Options options = sciqlop::parse_args(forwarded_argv(argc, argv));
#endif

    int round = 1;
    sciqlop::RoundKind kind = sciqlop::RoundKind::Start;
    std::vector<sciqlop::Clock::time_point> restart_times;

    for (;;) {
        auto ui = sciqlop::make_fltk_ui(splash_path());

        // A restart round is indistinguishable from a crash loop until it
        // has happened a few times — cap it here, before running another
        // session, rather than spinning forever.
        if (kind == sciqlop::RoundKind::Restart) {
            const auto now = sciqlop::Clock::now();
            restart_times.push_back(now);
            if (sciqlop::restart_budget_exhausted(restart_times, now)) {
                const std::string message =
                    "SciQLop keeps restarting (" + std::to_string(restart_times.size()) +
                    " times in 60 s); giving up.\n\nFull output: " +
                    sciqlop::paths::last_launch_log().string();
                ui->run_with_worker([&] { ui->post_error(message); });
                return 1;
            }
        }

        const sciqlop::SessionResult result = sciqlop::run_session(options, *ui, round, kind);

        if (result.exit_code == sciqlop::EXIT_RESTART) {
            options = sciqlop::options_for_next_round(std::move(options), result.exit_code,
                                                       result.switch_target);
            ++round;
            kind = sciqlop::RoundKind::Restart;
            continue;
        }

        if (result.exit_code == sciqlop::EXIT_SWITCH_WORKSPACE) {
            if (result.switch_target.empty()) return result.exit_code;
            options = sciqlop::options_for_next_round(std::move(options), result.exit_code,
                                                       result.switch_target);
            ++round;
            kind = sciqlop::RoundKind::Switch;
            continue;
        }

        return result.exit_code;
    }
}
