#include "launcher.hpp"
#include "paths.hpp"
#include "ui_fltk.hpp"

#include <filesystem>

namespace fs = std::filesystem;

namespace {

/// Splash artwork ships beside the launcher binary.
fs::path splash_path() { return sciqlop::paths::executable_dir() / "splash.png"; }

}  // namespace

int main(int argc, char** argv) {
    sciqlop::Options options = sciqlop::parse_args(argc, argv);

    for (;;) {
        auto ui = sciqlop::make_fltk_ui(splash_path());
        const sciqlop::SessionResult result = sciqlop::run_session(options, *ui);

        options.sciqlop_file.clear();  // consumed by the first round only

        if (result.exit_code == sciqlop::EXIT_RESTART) continue;

        if (result.exit_code == sciqlop::EXIT_SWITCH_WORKSPACE) {
            const std::string target = sciqlop::take_switch_target(result.workspace_dir);
            if (target.empty()) return result.exit_code;
            options.workspace = target;
            continue;
        }
        return result.exit_code;
    }
}
