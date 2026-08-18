// Unit tests for the launcher's pure logic — the parts that decide which
// workspace to open and what gets written into it. The UI and the subprocess
// layer are exercised by running the launcher, not from here.
#include "launcher.hpp"
#include "manifest.hpp"
#include "project.hpp"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>

namespace fs = std::filesystem;

namespace {

int failures = 0;

void check(bool condition, const std::string& what) {
    if (condition) return;
    std::cerr << "FAIL: " << what << '\n';
    ++failures;
}

void check_contains(const std::string& haystack, const std::string& needle) {
    check(haystack.find(needle) != std::string::npos, "expected to find: " + needle);
}

/// Temporary directory removed on scope exit, so a failing test cannot leak
/// state into the next one.
class TempDir {
public:
    TempDir() : path_(fs::temp_directory_path() / unique_name()) { fs::create_directories(path_); }
    ~TempDir() {
        std::error_code ec;
        fs::remove_all(path_, ec);
    }

    const fs::path& path() const { return path_; }

private:
    static std::string unique_name() {
        static int counter = 0;
        const auto stamp = std::chrono::steady_clock::now().time_since_epoch().count();
        return "sciqlop-launcher-test-" + std::to_string(counter++) + "-" +
               std::to_string(static_cast<long long>(stamp));
    }

    fs::path path_;
};

void write(const fs::path& path, const std::string& content) {
    fs::create_directories(path.parent_path());
    std::ofstream out(path, std::ios::binary | std::ios::trunc);
    out << content;
}

void test_manifest_reads_launcher_keys() {
    TempDir dir;
    write(dir.path() / "workspace.sciqlop",
          "[workspace]\n"
          "name = \"MMS study\"\n"
          "sciqlop_version = \"0.13.0\"\n"
          "python_version = \"3.14\"\n"
          "description = \"ignored by the launcher\"\n"
          "\n[dependencies]\nrequires = [\"spok\"]\n");

    const auto manifest = sciqlop::read_manifest(dir.path());
    check(manifest.has_value(), "manifest parses");
    check(manifest->name == "MMS study", "name read");
    check(manifest->sciqlop_version == "0.13.0", "sciqlop_version read");
    check(manifest->python_version == "3.14", "python_version read");
}

void test_manifest_absent_and_malformed() {
    TempDir dir;
    check(!sciqlop::read_manifest(dir.path()).has_value(), "missing manifest => nullopt");

    write(dir.path() / "workspace.sciqlop", "this is not = valid = toml [[[\n");
    check(!sciqlop::read_manifest(dir.path()).has_value(), "malformed manifest => nullopt");
}

void test_manifest_roundtrip_escapes_quotes() {
    TempDir dir;
    sciqlop::write_manifest(dir.path(), {"weird \"name\" \\ here", "0.13.0", ""});

    const auto manifest = sciqlop::read_manifest(dir.path());
    check(manifest.has_value(), "escaped manifest parses");
    check(manifest->name == "weird \"name\" \\ here", "quotes and backslashes survive");
    check(manifest->python_version.empty(), "omitted key reads back empty");
}

void test_pyproject_pins_requested_version() {
    const std::string pinned = sciqlop::render_pyproject({"My Study", "0.13.0", "3.14"});
    check_contains(pinned, "\"sciqlop==0.13.0\"");
    check_contains(pinned, "name = \"sciqlop-workspace-my-study\"");
    check_contains(pinned, "requires-python = \">=3.14\"");
    check_contains(pinned, "\"jupyqt\"");

    const std::string unpinned = sciqlop::render_pyproject({"x", "", "3.14"});
    check_contains(unpinned, "\"sciqlop\",");
    check(unpinned.find("sciqlop==") == std::string::npos, "no pin when version empty");
}

void test_pyproject_never_overwrites_the_apps_file() {
    TempDir dir;
    const std::string owned = "# written by SciQLop with plugin deps\n";
    write(dir.path() / "pyproject.toml", owned);

    const bool written = sciqlop::write_pyproject_if_missing(dir.path(), {"x", "0.13.0", "3.14"});
    check(!written, "existing pyproject is left alone");

    std::ifstream in(dir.path() / "pyproject.toml", std::ios::binary);
    const std::string content((std::istreambuf_iterator<char>(in)), {});
    check(content == owned, "app-owned dependencies survive");
}

void test_most_recently_used_picks_newest_marker() {
    TempDir root;
    for (const std::string name : {"old", "new", "no-marker"}) {
        write(root.path() / name / "workspace.sciqlop", "[workspace]\nname = \"" + name + "\"\n");
    }
    write(root.path() / "old" / ".last_used", "");
    write(root.path() / "new" / ".last_used", "");

    const auto old_time = fs::last_write_time(root.path() / "new" / ".last_used");
    fs::last_write_time(root.path() / "old" / ".last_used", old_time - std::chrono::hours(24));

    const auto recent = sciqlop::most_recently_used(root.path());
    check(recent.has_value(), "an MRU workspace is found");
    check(recent->filename() == "new", "newest .last_used wins");
}

void test_most_recently_used_ignores_unmarked_and_missing_root() {
    TempDir root;
    write(root.path() / "never-opened" / "workspace.sciqlop", "[workspace]\nname = \"x\"\n");
    check(!sciqlop::most_recently_used(root.path()).has_value(),
          "a workspace without .last_used is not a candidate");
    check(!sciqlop::most_recently_used(root.path() / "absent").has_value(),
          "missing root => nullopt");
}

void test_parse_args() {
    const char* argv[] = {"launcher", "--workspace", "study", "--sciqlop-version", "0.13.0"};
    const auto options = sciqlop::parse_args(5, const_cast<char**>(argv));
    check(options.workspace == "study", "--workspace parsed");
    check(options.sciqlop_version == "0.13.0", "--sciqlop-version parsed");
    check(options.sciqlop_file.empty(), "no positional file");

    const char* with_file[] = {"launcher", "/data/ws/workspace.sciqlop"};
    check(sciqlop::parse_args(2, const_cast<char**>(with_file)).sciqlop_file ==
              "/data/ws/workspace.sciqlop",
          "positional .sciqlop file parsed");
}

void test_resolve_workspace_dir_prefers_explicit_over_mru() {
    // "/absolute/workspace" is NOT absolute on Windows — without a drive letter
    // it is root-relative — so the literal has to differ per platform.
#ifdef _WIN32
    const std::string absolute = "C:/absolute/workspace";
#else
    const std::string absolute = "/absolute/workspace";
#endif
    sciqlop::Options options;
    options.workspace = absolute;
    check(sciqlop::resolve_workspace_dir(options) == fs::path(absolute),
          "absolute --workspace used as-is");

    sciqlop::Options named;
    named.workspace = "study";
    const fs::path resolved = sciqlop::resolve_workspace_dir(named);
    check(resolved.filename() == "study" && resolved.has_parent_path(),
          "a bare workspace name resolves under the workspaces root");

    sciqlop::Options from_file;
    from_file.sciqlop_file = "/data/ws/workspace.sciqlop";
    check(sciqlop::resolve_workspace_dir(from_file) == fs::path("/data/ws"),
          "a .sciqlop file resolves to its directory");
}

void test_switch_target_is_consumed_once() {
    TempDir dir;
    write(dir.path() / ".sciqlop_switch_target", "  other-workspace \n");

    check(sciqlop::take_switch_target(dir.path()) == "other-workspace", "target read and trimmed");
    check(sciqlop::take_switch_target(dir.path()).empty(), "target consumed after first read");
}

}  // namespace

int main() {
    test_manifest_reads_launcher_keys();
    test_manifest_absent_and_malformed();
    test_manifest_roundtrip_escapes_quotes();
    test_pyproject_pins_requested_version();
    test_pyproject_never_overwrites_the_apps_file();
    test_most_recently_used_picks_newest_marker();
    test_most_recently_used_ignores_unmarked_and_missing_root();
    test_parse_args();
    test_resolve_workspace_dir_prefers_explicit_over_mru();
    test_switch_target_is_consumed_once();

    if (failures == 0) std::cout << "all launcher core tests passed\n";
    return failures == 0 ? 0 : 1;
}
