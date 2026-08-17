// The launcher's slice of workspace.sciqlop.
//
// This is the frozen contract with the application: the launcher reads only
// these three keys and must keep reading them for every SciQLop version it can
// ever be asked to start. Everything else in the manifest belongs to the app.
#pragma once

#include <filesystem>
#include <optional>
#include <string>

namespace sciqlop {

struct Manifest {
    std::string name;
    std::string sciqlop_version;  ///< empty => resolve latest at creation time
    std::string python_version;   ///< empty => launcher default

    static constexpr const char* filename = "workspace.sciqlop";
};

/// Read the launcher-relevant keys. Returns nullopt when the file is missing or
/// unparseable — the caller decides whether that means "create a new workspace".
std::optional<Manifest> read_manifest(const std::filesystem::path& workspace_dir);

/// Write a minimal manifest for a freshly created workspace.
void write_manifest(const std::filesystem::path& workspace_dir, const Manifest& manifest);

/// Newest workspace directory by .last_used mtime, or nullopt when none exist.
std::optional<std::filesystem::path> most_recently_used(
    const std::filesystem::path& workspaces_root);

}  // namespace sciqlop
