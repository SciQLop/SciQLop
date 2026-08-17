// Bootstrap pyproject.toml generation.
//
// The launcher writes only enough to get SciQLop itself installed. Plugin
// dependencies, appstore packages and workspace `requires` are the app's
// business: it rewrites this file once running and asks for a restart (exit
// code 64) when the contents changed. Keeping that knowledge out of the
// launcher is what lets one launcher binary start every SciQLop version.
#pragma once

#include <filesystem>
#include <string>

namespace sciqlop {

struct BootstrapProject {
    std::string workspace_name;
    std::string sciqlop_version;  ///< empty => unpinned
    std::string python_version;   ///< e.g. "3.14"
};

std::string render_pyproject(const BootstrapProject& project);

/// Write pyproject.toml only when absent — an existing file is the app's, and
/// overwriting it would drop every plugin and appstore dependency.
/// Returns true when a file was written.
bool write_pyproject_if_missing(const std::filesystem::path& workspace_dir,
                               const BootstrapProject& project);

}  // namespace sciqlop
