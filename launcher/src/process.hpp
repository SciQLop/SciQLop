// Subprocess execution with line-streamed output.
//
// This is the piece Qt would have given us as QProcess. Only one shape is
// needed: a supervised run for the application itself, whose output is tee'd
// to a log while the caller watches for the startup-ready marker.
#pragma once

#include <filesystem>
#include <functional>
#include <map>
#include <string>
#include <vector>

namespace sciqlop {

using OutputSink = std::function<void(const std::string& line)>;

struct Command {
    std::vector<std::string> argv;
    std::map<std::string, std::string> extra_env;  ///< merged over the inherited env
};

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
