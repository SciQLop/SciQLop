// Unit tests for the launcher's pure logic — argv forwarding and the
// phase-line classifier. Everything else (the UI, the subprocess layer,
// workspace resolution, the ready-file handshake) is exercised end to end by
// smoke_test.sh, not from here.
#include "launcher.hpp"

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

void test_parse_args_forwards_argv_verbatim() {
    const std::vector<std::string> args = {"--workspace", "foo", "bar.sciqlop-archive"};
    const sciqlop::Options options = sciqlop::parse_args(args);
    check(options.forwarded_args == args, "forwarded_args is argv[1..] untouched, in order");
}

void test_parse_args_on_empty_argv() {
    const sciqlop::Options options = sciqlop::parse_args({});
    check(options.forwarded_args.empty(), "no arguments forwards nothing");
}

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

}  // namespace

int main() {
    test_parse_args_forwards_argv_verbatim();
    test_parse_args_on_empty_argv();
    test_phase_for_line_matches_starting_exactly();
    test_phase_for_line_matches_preparing_workspace_prefix_and_suffix();
    test_phase_for_line_ignores_unrelated_lines();

    if (failures == 0) std::cout << "all launcher core tests passed\n";
    return failures == 0 ? 0 : 1;
}
