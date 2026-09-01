// The launcher's entire view of its UI toolkit.
//
// Swapping FLTK for Qt (or anything else) means writing one more implementation
// of this interface; nothing else in the launcher changes.
#pragma once

#include <functional>
#include <string>

namespace sciqlop {

class Ui {
public:
    virtual ~Ui() = default;

    /// Run *work* on a worker thread while the event loop spins here, and
    /// return once *work* has finished and the window has closed. The post_*
    /// methods are the only ones *work* may call.
    virtual void run_with_worker(std::function<void()> work) = 0;

    virtual void post_phase(const std::string& text) = 0;
    virtual void post_detail(const std::string& text) = 0;
    virtual void post_progress(double percent) = 0;

    /// Non-blocking advisory banner; the user dismisses it while work continues.
    virtual void post_warning(const std::string& message) = 0;

    /// Terminal state: replaces the splash and keeps the window up until the
    /// user quits, so a failed launch can never disappear silently.
    virtual void post_error(const std::string& text) = 0;

    /// Hide the splash immediately — e.g. once the real app window is up —
    /// without waiting for run_with_worker's *work* to return (which only
    /// happens once the supervised app process exits entirely). Safe to call
    /// more than once; a no-op after post_error(), since only the user may
    /// dismiss an error.
    virtual void dismiss() = 0;
};

}  // namespace sciqlop
