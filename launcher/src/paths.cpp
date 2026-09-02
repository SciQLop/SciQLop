#include "paths.hpp"

#include <cstdlib>

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#elif defined(__APPLE__)
#include <mach-o/dyld.h>
#include <vector>
#endif

namespace fs = std::filesystem;

namespace sciqlop::paths {
namespace {

fs::path env_path(const char* name) {
    const char* value = std::getenv(name);
    return (value != nullptr && *value != '\0') ? fs::path(value) : fs::path();
}

fs::path home() {
#ifdef _WIN32
    if (auto profile = env_path("USERPROFILE"); !profile.empty()) return profile;
    return fs::path("C:/");
#else
    if (auto h = env_path("HOME"); !h.empty()) return h;
    return fs::path("/");
#endif
}

}  // namespace

fs::path user_data_dir() {
#if defined(_WIN32)
    auto base = env_path("LOCALAPPDATA");
    if (base.empty()) base = home() / "AppData" / "Local";
    return base / "LPP" / "sciqlop";
#elif defined(__APPLE__)
    return home() / "Library" / "Application Support" / "sciqlop";
#else
    auto base = env_path("XDG_DATA_HOME");
    if (base.empty()) base = home() / ".local" / "share";
    return base / "sciqlop";
#endif
}

fs::path last_launch_log() { return user_data_dir() / "last-launch.log"; }

fs::path executable_dir() {
    std::error_code ec;
#if defined(_WIN32)
    std::wstring buffer(MAX_PATH, L'\0');
    const DWORD size = GetModuleFileNameW(nullptr, buffer.data(),
                                          static_cast<DWORD>(buffer.size()));
    if (size > 0) return fs::path(buffer.substr(0, size)).parent_path();
#elif defined(__APPLE__)
    uint32_t size = 0;
    _NSGetExecutablePath(nullptr, &size);
    std::string buffer(size, '\0');
    if (_NSGetExecutablePath(buffer.data(), &size) == 0)
        return fs::canonical(fs::path(buffer.c_str()), ec).parent_path();
#else
    if (auto self = fs::read_symlink("/proc/self/exe", ec); !ec)
        return self.parent_path();
#endif
    return fs::current_path(ec);
}

}  // namespace sciqlop::paths
