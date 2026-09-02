// Unit tests for the launcher's pure logic — argv splitting/rebuilding, the
// phase-line classifier, and the switch-target handoff file. Everything else
// (the UI, the subprocess layer, workspace resolution, the ready-file
// handshake, the round loop itself) is exercised end to end by
// smoke_test.sh, not from here.
#include "launcher.hpp"

#include <chrono>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

namespace {

int failures = 0;

void check(bool condition, const std::string& what) {
    if (condition) return;
    std::cerr << "FAIL: " << what << '\n';
    ++failures;
}

// --- parse_args --------------------------------------------------------

void test_parse_args_splits_workspace_file_and_passthrough() {
    const sciqlop::Options options = sciqlop::parse_args(
        {"--sciqlop-version", "1.2.3", "--workspace", "foo", "bar.sciqlop-archive"});
    check(options.workspace == "foo", "--workspace value captured");
    check(options.sciqlop_file == "bar.sciqlop-archive", "positional file captured");
    check(options.passthrough == std::vector<std::string>{"--sciqlop-version", "1.2.3"},
          "unrecognized flag and its value land in passthrough, in order");
}

void test_parse_args_short_workspace_flag() {
    const sciqlop::Options options = sciqlop::parse_args({"-w", "my-study"});
    check(options.workspace == "my-study", "-w is accepted like --workspace");
    check(options.passthrough.empty(), "no passthrough left over");
}

void test_parse_args_on_empty_argv() {
    const sciqlop::Options options = sciqlop::parse_args({});
    check(options.workspace.empty(), "no workspace");
    check(options.sciqlop_file.empty(), "no file");
    check(options.passthrough.empty(), "no passthrough");
}

// --- app_argv (command building) ---------------------------------------

void test_app_argv_round_one_matches_user_argv_order() {
    // User typed exactly "--workspace foo bar.sciqlop-archive" — round 1 must
    // forward that untouched.
    sciqlop::Options options;
    options.workspace = "foo";
    options.sciqlop_file = "bar.sciqlop-archive";
    const std::vector<std::string> argv = sciqlop::app_argv(options);
    check(argv == std::vector<std::string>{"--workspace", "foo", "bar.sciqlop-archive"},
          "round 1 forwards --workspace <ws> <file> in the order the user typed it");
}

void test_app_argv_switch_round_drops_the_file_and_uses_the_target() {
    // A switch round: sciqlop_file has been cleared, workspace replaced by
    // the handoff target — the original positional file must not reappear.
    sciqlop::Options options;
    options.workspace = "other-workspace";
    const std::vector<std::string> argv = sciqlop::app_argv(options);
    check(argv == std::vector<std::string>{"--workspace", "other-workspace"},
          "switch round forwards --workspace <target> only, no positional file");
}

void test_app_argv_keeps_passthrough_ahead_of_workspace_and_file() {
    sciqlop::Options options;
    options.passthrough = {"--sciqlop-version", "1.2.3"};
    options.workspace = "foo";
    options.sciqlop_file = "study.sciqlop";
    const std::vector<std::string> argv = sciqlop::app_argv(options);
    check(argv == std::vector<std::string>{"--sciqlop-version", "1.2.3", "--workspace", "foo",
                                            "study.sciqlop"},
          "passthrough args precede --workspace and the positional file");
}

void test_app_argv_omits_absent_workspace_and_file() {
    sciqlop::Options options;
    options.passthrough = {"--sciqlop-version", "1.2.3"};
    const std::vector<std::string> argv = sciqlop::app_argv(options);
    check(argv == std::vector<std::string>{"--sciqlop-version", "1.2.3"},
          "no --workspace/file emitted when both are empty");
}

// --- phase_for_line ------------------------------------------------------

void test_phase_for_line_matches_starting_exactly() {
    check(sciqlop::phase_for_line("Starting SciQLop ...") == "Starting SciQLop",
          "exact 'Starting SciQLop ...' line recognized");
    check(!sciqlop::phase_for_line("Starting SciQLop").has_value(),
          "'Starting SciQLop' without the trailing ellipsis is not a phase line");
    check(!sciqlop::phase_for_line("Starting SciQLop now ...").has_value(),
          "extra words break the exact match");
}

void test_phase_for_line_matches_preparing_workspace_prefix_and_suffix() {
    check(sciqlop::phase_for_line("Preparing workspace /home/x/ws ...") == "Preparing workspace",
          "'Preparing workspace <path> ...' recognized regardless of the path in the middle");
    check(!sciqlop::phase_for_line("Preparing workspace").has_value(),
          "prefix alone, missing the ' ...' suffix, is not a phase line");
    check(!sciqlop::phase_for_line("preparing workspace /x ...").has_value(),
          "match is case sensitive");
}

void test_phase_for_line_ignores_unrelated_lines() {
    check(!sciqlop::phase_for_line("").has_value(), "empty line is not a phase line");
    check(!sciqlop::phase_for_line("Traceback (most recent call last):").has_value(),
          "an unrelated line is not a phase line");
}

// --- options_for_next_round ------------------------------------------------

void test_options_for_next_round_restart_keeps_everything() {
    sciqlop::Options options;
    options.workspace = "foo";
    options.sciqlop_file = "bar.sciqlop-archive";
    options.passthrough = {"--sciqlop-version", "1.2.3"};

    const sciqlop::Options next =
        sciqlop::options_for_next_round(options, sciqlop::EXIT_RESTART, "");

    check(next.workspace == "foo", "restart keeps the workspace");
    check(next.sciqlop_file == "bar.sciqlop-archive", "restart keeps the positional file");
    check(next.passthrough == options.passthrough, "restart keeps passthrough args");
}

void test_options_for_next_round_switch_replaces_workspace_and_drops_file() {
    sciqlop::Options options;
    options.workspace = "foo";
    options.sciqlop_file = "bar.sciqlop-archive";

    const sciqlop::Options next = sciqlop::options_for_next_round(
        options, sciqlop::EXIT_SWITCH_WORKSPACE, "other-workspace");

    check(next.workspace == "other-workspace",
          "switch replaces the workspace with the handoff target");
    check(next.sciqlop_file.empty(), "switch drops the positional file");
}

// --- restart_budget_exhausted -----------------------------------------------

void test_restart_budget_three_in_window_is_fine() {
    const auto now = sciqlop::Clock::now();
    const std::vector<sciqlop::Clock::time_point> restarts = {
        now - std::chrono::seconds(50), now - std::chrono::seconds(20), now};
    check(!sciqlop::restart_budget_exhausted(restarts, now),
          "3 restarts within 60s is not exhausted");
}

void test_restart_budget_fourth_in_window_is_exhausted() {
    const auto now = sciqlop::Clock::now();
    const std::vector<sciqlop::Clock::time_point> restarts = {
        now - std::chrono::seconds(55), now - std::chrono::seconds(40),
        now - std::chrono::seconds(10), now};
    check(sciqlop::restart_budget_exhausted(restarts, now),
          "4th restart within 60s exhausts the budget");
}

void test_restart_budget_ignores_restarts_outside_window() {
    const auto now = sciqlop::Clock::now();
    const std::vector<sciqlop::Clock::time_point> restarts = {
        now - std::chrono::seconds(120), now - std::chrono::seconds(50),
        now - std::chrono::seconds(20), now};
    check(!sciqlop::restart_budget_exhausted(restarts, now),
          "a restart older than the 60s window is forgotten");
}

// --- take_switch_target ---------------------------------------------------

std::filesystem::path make_tmp_dir() {
    static int counter = 0;
    const auto salt = std::chrono::steady_clock::now().time_since_epoch().count();
    const auto dir = std::filesystem::temp_directory_path() /
                     ("launcher_core_test_" + std::to_string(++counter) + "_" +
                      std::to_string(salt));
    std::filesystem::create_directories(dir);
    return dir;
}

void write_file(const std::filesystem::path& path, const std::string& content) {
    std::ofstream out(path, std::ios::binary);
    out << content;
}

void test_take_switch_target_missing_file() {
    const auto dir = make_tmp_dir();
    const auto handoff = dir / "missing";
    check(sciqlop::take_switch_target(handoff).empty(), "missing handoff file yields empty target");
}

void test_take_switch_target_empty_file_is_removed() {
    const auto dir = make_tmp_dir();
    const auto handoff = dir / "empty";
    write_file(handoff, "");
    check(sciqlop::take_switch_target(handoff).empty(), "empty handoff file yields empty target");
    check(!std::filesystem::exists(handoff), "empty handoff file is removed after being read");
}

void test_take_switch_target_trims_and_removes() {
    const auto dir = make_tmp_dir();
    const auto handoff = dir / "target";
    write_file(handoff, "  foo\n");
    check(sciqlop::take_switch_target(handoff) == "foo", "surrounding whitespace is trimmed");
    check(!std::filesystem::exists(handoff), "handoff file is removed after being read");
}

}  // namespace

int main() {
    test_parse_args_splits_workspace_file_and_passthrough();
    test_parse_args_short_workspace_flag();
    test_parse_args_on_empty_argv();
    test_app_argv_round_one_matches_user_argv_order();
    test_app_argv_switch_round_drops_the_file_and_uses_the_target();
    test_app_argv_keeps_passthrough_ahead_of_workspace_and_file();
    test_app_argv_omits_absent_workspace_and_file();
    test_options_for_next_round_restart_keeps_everything();
    test_options_for_next_round_switch_replaces_workspace_and_drops_file();
    test_restart_budget_three_in_window_is_fine();
    test_restart_budget_fourth_in_window_is_exhausted();
    test_restart_budget_ignores_restarts_outside_window();
    test_phase_for_line_matches_starting_exactly();
    test_phase_for_line_matches_preparing_workspace_prefix_and_suffix();
    test_phase_for_line_ignores_unrelated_lines();
    test_take_switch_target_missing_file();
    test_take_switch_target_empty_file_is_removed();
    test_take_switch_target_trims_and_removes();

    if (failures == 0) std::cout << "all launcher core tests passed\n";
    return failures == 0 ? 0 : 1;
}
