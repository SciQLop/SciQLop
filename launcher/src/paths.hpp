// Platform data locations, matching what platformdirs returns for the Python
// side (appname="sciqlop", appauthor="LPP") — only last-launch.log is shared
// between the two; workspace resolution itself is entirely Python's.
#pragma once

#include <filesystem>

namespace sciqlop::paths {

/// ~/.local/share/sciqlop | ~/Library/Application Support/sciqlop |
/// %LOCALAPPDATA%\LPP\sciqlop
std::filesystem::path user_data_dir();

std::filesystem::path last_launch_log();

/// Directory holding the running launcher binary; bundled uv and node sit
/// beside it, so every lookup of them is relative to this.
std::filesystem::path executable_dir();

}  // namespace sciqlop::paths
