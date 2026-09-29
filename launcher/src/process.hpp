// Subprocess execution with line-streamed output.
//
// This is the piece Qt would have given us as QProcess. Only one shape is
// needed: a supervised run for the application itself, whose output is tee'd
// to a log while the caller watches for the startup-ready marker.
#pragma once

#include <cctype>
#include <chrono>
#include <cstdio>
#include <ctime>
#include <filesystem>
#include <functional>
#include <map>
#include <string>
#include <vector>

namespace sciqlop {

using OutputSink = std::function<void(const std::string& line)>;

struct Command {
    std::vector<std::string> argv;
    /// Each entry here *replaces* any inherited environment entry with the
    /// same name — it does not merge into it (see process_posix.cpp's
    /// merged_environment() / process_win32.cpp's build_environment()). A
    /// caller that wants to prepend to e.g. PATH must read the inherited
    /// value itself and build the full replacement string.
    std::map<std::string, std::string> extra_env;
};

/// Uppercases ASCII letters. Environment variable names are case-insensitive
/// on Windows (the OS itself folds "Path"/"PATH"/"path" to the same entry)
/// but case-sensitive on POSIX — process_win32.cpp's build_environment()
/// uses this to compare an override's key against each inherited entry's key
/// so e.g. an override named "PATH" correctly replaces an inherited "Path"
/// instead of both ending up in the child's environment block with which one
/// wins left undefined. Pure and platform-independent so it's unit-testable
/// without a Windows build; process_posix.cpp has no use for it.
inline std::string env_key_upper(const std::string& key) {
    std::string upper = key;
    for (char& c : upper) c = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
    return upper;
}

/// "YYYY-MM-DD HH:MM:SS.mmm" in local time: the prefix of every line tee'd to
/// the session log, so a crash can be placed relative to the last lines
/// before it. sciqlop_launcher.py writes the same format.
inline std::string log_timestamp(std::chrono::system_clock::time_point when) {
    const std::time_t seconds = std::chrono::system_clock::to_time_t(when);
    const auto millis = std::chrono::duration_cast<std::chrono::milliseconds>(
                            when.time_since_epoch()).count() % 1000;
    std::tm local{};
#ifdef _WIN32
    localtime_s(&local, &seconds);
#else
    localtime_r(&seconds, &local);
#endif
    char buffer[32];
    const size_t length = std::strftime(buffer, sizeof buffer, "%Y-%m-%d %H:%M:%S", &local);
    std::snprintf(buffer + length, sizeof buffer - length, ".%03d", static_cast<int>(millis));
    return buffer;
}

/// Run to completion, tee-ing stdout and stderr to *log_file*. Both streams are
/// also handed line by line to *on_stdout* / *on_stderr* — the supervised child
/// here is SciQLop.app (see sciqlop_launcher.py), whose own progress output
/// (e.g. "Preparing workspace ...", "Starting SciQLop ...") is plain stdout,
/// not stderr, so a caller that only wants a crash-report tail should collect
/// that itself from *on_stderr* rather than assume progress lines land there.
/// *on_tick* fires roughly every 100 ms while the process lives, which is how
/// the caller notices the startup-ready marker and closes the splash.
/// Returns the exit code, or -1 if the process could not be started.
int run_supervised(const Command& command,
                   const std::filesystem::path& log_file,
                   const OutputSink& on_stdout,
                   const OutputSink& on_stderr,
                   const std::function<void()>& on_tick);

}  // namespace sciqlop
