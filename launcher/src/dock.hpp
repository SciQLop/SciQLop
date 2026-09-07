#pragma once

/// Whether this launcher process shows in the Dock / Cmd+Tab switcher.
///
/// Once the splash is dismissed the launcher has no window for the rest of
/// the session but stays alive to supervise restart/switch rounds. On macOS
/// that leaves a "SciQLop" Cmd+Tab entry that brings nothing to front, right
/// next to the GUI's own entry — so the launcher steps out of the Dock while
/// hidden and back in whenever it has a window to show. No-op elsewhere.
namespace dock {
void set_visible(bool visible);
}
