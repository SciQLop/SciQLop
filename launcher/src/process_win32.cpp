#include "process.hpp"

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <fstream>
#include <set>

namespace fs = std::filesystem;

namespace sciqlop {
namespace {

std::wstring widen(const std::string& utf8) {
    if (utf8.empty()) return {};
    const int size = MultiByteToWideChar(CP_UTF8, 0, utf8.data(),
                                         static_cast<int>(utf8.size()), nullptr, 0);
    std::wstring wide(static_cast<size_t>(size), L'\0');
    MultiByteToWideChar(CP_UTF8, 0, utf8.data(), static_cast<int>(utf8.size()),
                        wide.data(), size);
    return wide;
}

/// CommandLineToArgvW quoting rules: backslashes are only special immediately
/// before a quote, where they must be doubled.
std::wstring quote_argument(const std::wstring& arg) {
    if (!arg.empty() && arg.find_first_of(L" \t\"") == std::wstring::npos) return arg;

    std::wstring quoted = L"\"";
    size_t backslashes = 0;
    for (wchar_t c : arg) {
        if (c == L'\\') {
            ++backslashes;
            continue;
        }
        if (c == L'"') {
            quoted.append(backslashes * 2 + 1, L'\\');
            backslashes = 0;
        } else if (backslashes > 0) {
            quoted.append(backslashes, L'\\');
            backslashes = 0;
        }
        quoted += c;
    }
    quoted.append(backslashes * 2, L'\\');
    return quoted + L'"';
}

std::wstring build_command_line(const std::vector<std::string>& argv) {
    std::wstring line;
    for (const auto& arg : argv) {
        if (!line.empty()) line += L' ';
        line += quote_argument(widen(arg));
    }
    return line;
}

/// Null-separated, double-null-terminated block of the inherited environment
/// with *overrides* applied. Each override *replaces* its same-named
/// inherited entry (see process.hpp's Command::extra_env doc) rather than
/// adding a second entry — matched case-insensitively via env_key_upper()
/// since Windows env var names are case-insensitive (e.g. the OS's own PATH
/// entry is actually spelled "Path"), unlike the map key comparison below
/// which would otherwise miss it.
std::wstring build_environment(const std::map<std::string, std::string>& overrides) {
    std::set<std::string> override_keys_upper;
    for (const auto& [key, value] : overrides) override_keys_upper.insert(env_key_upper(key));

    std::wstring block;
    if (LPWCH inherited = GetEnvironmentStringsW(); inherited != nullptr) {
        for (LPWCH entry = inherited; *entry != L'\0';) {
            const std::wstring item(entry);
            entry += item.size() + 1;
            const auto eq = item.find(L'=');
            if (eq == std::wstring::npos || eq == 0) continue;  // drive-letter entries
            std::wstring key = item.substr(0, eq);
            std::string narrow_key;
            for (wchar_t c : key) narrow_key += static_cast<char>(c);
            if (override_keys_upper.count(env_key_upper(narrow_key)) != 0) continue;
            block += item;
            block += L'\0';
        }
        FreeEnvironmentStringsW(inherited);
    }
    for (const auto& [key, value] : overrides) {
        block += widen(key) + L'=' + widen(value);
        block += L'\0';
    }
    block += L'\0';
    return block;
}

class LineSplitter {
public:
    void feed(const char* data, size_t size, const OutputSink& sink) {
        buffer_.append(data, size);
        size_t start = 0;
        for (size_t i = 0; i < buffer_.size(); ++i) {
            if (buffer_[i] != '\n') continue;
            emit(buffer_.substr(start, i - start), sink);
            start = i + 1;
        }
        buffer_.erase(0, start);
    }

    void flush(const OutputSink& sink) {
        if (!buffer_.empty()) emit(buffer_, sink);
        buffer_.clear();
    }

private:
    static void emit(std::string line, const OutputSink& sink) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (sink) sink(line);
    }

    std::string buffer_;
};

struct Pipe {
    HANDLE read = nullptr;
    HANDLE write = nullptr;
};

bool create_pipe(Pipe& pipe) {
    SECURITY_ATTRIBUTES attributes{sizeof(SECURITY_ATTRIBUTES), nullptr, TRUE};
    if (CreatePipe(&pipe.read, &pipe.write, &attributes, 0) == 0) return false;
    SetHandleInformation(pipe.read, HANDLE_FLAG_INHERIT, 0);
    return true;
}

/// Drain whatever is buffered without blocking; returns false once the pipe is
/// closed by the writer.
bool drain(HANDLE handle, LineSplitter& splitter, const OutputSink& sink) {
    DWORD available = 0;
    if (PeekNamedPipe(handle, nullptr, 0, nullptr, &available, nullptr) == 0) return false;
    while (available > 0) {
        char buffer[4096];
        DWORD read_bytes = 0;
        const DWORD wanted = available < sizeof(buffer) ? available : sizeof(buffer);
        if (ReadFile(handle, buffer, wanted, &read_bytes, nullptr) == 0 || read_bytes == 0)
            return false;
        splitter.feed(buffer, read_bytes, sink);
        available -= read_bytes;
    }
    return true;
}

int pump(PROCESS_INFORMATION process,
         HANDLE stdout_read,
         HANDLE stderr_read,
         const OutputSink& on_stdout,
         const OutputSink& on_stderr,
         const std::function<void()>& on_tick) {
    LineSplitter out_lines;
    LineSplitter err_lines;
    bool open_out = true;
    bool open_err = true;

    for (;;) {
        if (open_out) open_out = drain(stdout_read, out_lines, on_stdout);
        if (open_err) open_err = drain(stderr_read, err_lines, on_stderr);
        if (on_tick) on_tick();

        const DWORD state = WaitForSingleObject(process.hProcess, 50);
        if (state != WAIT_TIMEOUT) {
            drain(stdout_read, out_lines, on_stdout);
            drain(stderr_read, err_lines, on_stderr);
            break;
        }
    }
    out_lines.flush(on_stdout);
    err_lines.flush(on_stderr);

    DWORD code = 0;
    GetExitCodeProcess(process.hProcess, &code);
    CloseHandle(process.hProcess);
    CloseHandle(process.hThread);
    CloseHandle(stdout_read);
    CloseHandle(stderr_read);
    return static_cast<int>(code);
}

int spawn_and_pump(const Command& command,
                   const OutputSink& on_stdout,
                   const OutputSink& on_stderr,
                   const std::function<void()>& on_tick) {
    Pipe out_pipe;
    Pipe err_pipe;
    if (!create_pipe(out_pipe)) return -1;
    if (!create_pipe(err_pipe)) {
        CloseHandle(out_pipe.read);
        CloseHandle(out_pipe.write);
        return -1;
    }

    STARTUPINFOW startup{};
    startup.cb = sizeof(startup);
    startup.dwFlags = STARTF_USESTDHANDLES;
    startup.hStdOutput = out_pipe.write;
    startup.hStdError = err_pipe.write;
    startup.hStdInput = GetStdHandle(STD_INPUT_HANDLE);

    std::wstring command_line = build_command_line(command.argv);
    std::wstring environment = build_environment(command.extra_env);

    PROCESS_INFORMATION process{};
    const BOOL started = CreateProcessW(
        nullptr, command_line.data(), nullptr, nullptr, TRUE,
        CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT, environment.data(),
        nullptr, &startup, &process);

    CloseHandle(out_pipe.write);
    CloseHandle(err_pipe.write);
    if (started == 0) {
        CloseHandle(out_pipe.read);
        CloseHandle(err_pipe.read);
        return -1;
    }
    return pump(process, out_pipe.read, err_pipe.read, on_stdout, on_stderr, on_tick);
}

}  // namespace

int run_supervised(const Command& command,
                   const fs::path& log_file,
                   const OutputSink& on_stdout,
                   const OutputSink& on_stderr,
                   const std::function<void()>& on_tick) {
    std::ofstream log(log_file, std::ios::binary | std::ios::app);
    log << "$ ";
    for (const auto& arg : command.argv) log << arg << ' ';
    log << '\n' << std::flush;

    auto tee = [&log](const char* label, const std::string& line) {
        log << '[' << label << "] " << line << '\n' << std::flush;
    };

    return spawn_and_pump(
        command,
        [&](const std::string& line) {
            tee("out", line);
            if (on_stdout) on_stdout(line);
        },
        [&](const std::string& line) {
            tee("err", line);
            if (on_stderr) on_stderr(line);
        },
        on_tick);
}

}  // namespace sciqlop
