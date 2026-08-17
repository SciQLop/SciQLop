// Workspace preparation and application supervision.
//
// Everything here is toolkit-independent: it talks to the UI only through the
// Ui interface, so the FLTK front end can be swapped without touching it.
#pragma once

#include "ui.hpp"

#include <filesystem>
#include <string>

namespace sciqlop {

/// Exit codes the application uses to ask the launcher for another round.
inline constexpr int EXIT_RESTART = 64;
inline constexpr int EXIT_SWITCH_WORKSPACE = 65;

struct Options {
    std::string workspace;        ///< name or absolute path; empty => resolve
    std::string sciqlop_file;     ///< a .sciqlop file to open
    std::string sciqlop_version;  ///< --sciqlop-version override
};

struct SessionResult {
    int exit_code = 0;
    std::filesystem::path workspace_dir;
};

Options parse_args(int argc, char** argv);

std::filesystem::path resolve_workspace_dir(const Options& options);

/// Prepare the workspace and run the application to completion, driving *ui*.
SessionResult run_session(const Options& options, Ui& ui);

/// Read and consume the switch-workspace target written by the application.
std::string take_switch_target(const std::filesystem::path& workspace_dir);

/// Warning text when libxcb-cursor is missing on Linux, empty otherwise.
std::string xcb_cursor_warning();

}  // namespace sciqlop
