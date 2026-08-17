#include "manifest.hpp"

#include <toml++/toml.hpp>

#include <fstream>

namespace fs = std::filesystem;

namespace sciqlop {
namespace {

std::string string_or_empty(const toml::table& table, std::string_view key) {
    return table[key].value_or(std::string{});
}

/// TOML basic-string escaping. Workspace names are user-provided and routinely
/// contain quotes or backslashes on Windows paths.
std::string escape(const std::string& value) {
    std::string out;
    out.reserve(value.size());
    for (char c : value) {
        switch (c) {
            case '"':  out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:   out += c; break;
        }
    }
    return out;
}

}  // namespace

std::optional<Manifest> read_manifest(const fs::path& workspace_dir) {
    const fs::path path = workspace_dir / Manifest::filename;
    std::error_code ec;
    if (!fs::is_regular_file(path, ec)) return std::nullopt;

    toml::table root;
    try {
        root = toml::parse_file(path.string());
    } catch (const toml::parse_error&) {
        return std::nullopt;
    }

    const auto* workspace = root["workspace"].as_table();
    if (workspace == nullptr) return std::nullopt;

    Manifest manifest;
    manifest.name = string_or_empty(*workspace, "name");
    manifest.sciqlop_version = string_or_empty(*workspace, "sciqlop_version");
    manifest.python_version = string_or_empty(*workspace, "python_version");
    if (manifest.name.empty()) manifest.name = workspace_dir.filename().string();
    return manifest;
}

void write_manifest(const fs::path& workspace_dir, const Manifest& manifest) {
    fs::create_directories(workspace_dir);
    std::ofstream out(workspace_dir / Manifest::filename, std::ios::binary | std::ios::trunc);
    out << "[workspace]\n";
    out << "name = \"" << escape(manifest.name) << "\"\n";
    if (!manifest.sciqlop_version.empty())
        out << "sciqlop_version = \"" << escape(manifest.sciqlop_version) << "\"\n";
    if (!manifest.python_version.empty())
        out << "python_version = \"" << escape(manifest.python_version) << "\"\n";
}

std::optional<fs::path> most_recently_used(const fs::path& workspaces_root) {
    std::error_code ec;
    if (!fs::is_directory(workspaces_root, ec)) return std::nullopt;

    std::optional<fs::path> newest;
    fs::file_time_type newest_time{};
    for (const auto& entry : fs::directory_iterator(workspaces_root, ec)) {
        if (!entry.is_directory(ec)) continue;
        if (!fs::is_regular_file(entry.path() / Manifest::filename, ec)) continue;

        const fs::path marker = entry.path() / ".last_used";
        if (!fs::is_regular_file(marker, ec)) continue;
        const auto stamp = fs::last_write_time(marker, ec);
        if (ec) continue;
        if (!newest || stamp > newest_time) {
            newest = entry.path();
            newest_time = stamp;
        }
    }
    return newest;
}

}  // namespace sciqlop
