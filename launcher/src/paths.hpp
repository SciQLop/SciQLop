// Platform data locations, matching what platformdirs returns for the Python
// side (appname="sciqlop", appauthor="LPP"). The two must agree or the launcher
// and the app will disagree about where workspaces live.
#pragma once

#include <filesystem>

namespace sciqlop::paths {

/// ~/.local/share/sciqlop | ~/Library/Application Support/sciqlop |
/// %LOCALAPPDATA%\LPP\sciqlop
std::filesystem::path user_data_dir();

std::filesystem::path workspaces_root();
std::filesystem::path last_launch_log();

/// Optional launcher-owned overrides, written by the app when the corresponding
/// settings change. Absent on a fresh install, which is not an error.
std::filesystem::path launcher_config();

/// Directory holding the running launcher binary; bundled uv and node sit
/// beside it, so every lookup of them is relative to this.
std::filesystem::path executable_dir();

}  // namespace sciqlop::paths
