#pragma once

#include "ui.hpp"

#include <filesystem>
#include <memory>

namespace sciqlop {

/// FLTK implementation of Ui. The splash artwork is loaded from *splash_png*;
/// a missing file degrades to the caption strip alone rather than failing.
std::unique_ptr<Ui> make_fltk_ui(const std::filesystem::path& splash_png);

}  // namespace sciqlop
