// Platform data locations, matching what platformdirs returns for the Python
// side (appname="sciqlop", appauthor="LPP") — only last-launch.log is shared
// between the two; workspace resolution itself is entirely Python's.
#pragma once

#include <filesystem>
#include <optional>
#include <string>

namespace sciqlop::paths {

/// ~/.local/share/sciqlop | ~/Library/Application Support/sciqlop |
/// %LOCALAPPDATA%\LPP\sciqlop
std::filesystem::path user_data_dir();

std::filesystem::path last_launch_log();

/// Directory holding the running launcher binary; bundled uv and node sit
/// beside it, so every lookup of them is relative to this.
std::filesystem::path executable_dir();

/// PATH's own entry separator: ';' on Windows, ':' elsewhere.
#if defined(_WIN32)
inline constexpr char PATH_LIST_SEPARATOR = ';';
#else
inline constexpr char PATH_LIST_SEPARATOR = ':';
#endif

/// The self-contained Windows bundle places a full Python install right next
/// to the launcher (`<exe_dir>/python/python.exe`; POSIX equivalent
/// `<exe_dir>/python/bin/python3`, unused today but exercised by the unit
/// tests) — this is what lets the launcher be the package's entry point
/// there instead of relying on AppRun/a wrapper script to have already put
/// an interpreter on PATH (the AppImage and macOS layouts keep Python
/// elsewhere and always take that PATH route). Returns nullopt when there is
/// no such file next to *exe_dir*.
std::optional<std::filesystem::path> bundled_python(const std::filesystem::path& exe_dir);

/// PATH entries to prepend when running the interpreter `bundled_python()`
/// found: the bundled `node` and `uv` directories, then the interpreter's own
/// Scripts (Windows) / bin (POSIX) directory — joined with
/// PATH_LIST_SEPARATOR. Mirrors the PATH the old scripts/windows/launcher.c
/// built by hand.
std::string bundled_path_prefix(const std::filesystem::path& exe_dir);

}  // namespace sciqlop::paths
