// Subprocess execution with line-streamed output.
//
// This is the piece Qt would have given us as QProcess. Two shapes are needed:
// a blocking run for `uv` (whose stderr drives the splash detail line), and a
// supervised run for the application itself (whose output is tee'd to a log
// while the caller watches for the startup-ready marker).
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
    std::filesystem::path working_dir;             ///< empty => inherit
    std::map<std::string, std::string> extra_env;  ///< merged over the inherited env
};

/// Run to completion, delivering stderr line by line to *on_line*.
/// Returns the exit code, or -1 if the process could not be started.
int run(const Command& command, const OutputSink& on_line);

/// Run to completion, tee-ing stdout and stderr to *log_file*. Stderr lines are
/// also handed to *on_stderr* so the caller can keep a tail for error reporting.
/// *on_tick* fires roughly every 100 ms while the process lives, which is how
/// the caller notices the startup-ready marker and closes the splash.
/// Returns the exit code, or -1 if the process could not be started.
int run_supervised(const Command& command,
                   const std::filesystem::path& log_file,
                   const OutputSink& on_stderr,
                   const std::function<void()>& on_tick);

}  // namespace sciqlop
