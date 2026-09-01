#include "process.hpp"

#include <poll.h>
#include <spawn.h>
#include <sys/wait.h>
#include <unistd.h>

#include <cerrno>
#include <cstring>
#include <fstream>

extern char** environ;

namespace fs = std::filesystem;

namespace sciqlop {
namespace {

/// Full environment for the child: the inherited one with *overrides* applied.
/// Built in the parent so the child does nothing but exec after forking.
std::vector<std::string> merged_environment(
    const std::map<std::string, std::string>& overrides) {
    std::vector<std::string> entries;
    for (char** e = environ; *e != nullptr; ++e) {
        const std::string entry(*e);
        const auto eq = entry.find('=');
        const std::string key = entry.substr(0, eq);
        if (overrides.count(key) == 0) entries.push_back(entry);
    }
    for (const auto& [key, value] : overrides) entries.push_back(key + "=" + value);
    return entries;
}

std::vector<char*> as_c_array(const std::vector<std::string>& values) {
    std::vector<char*> pointers;
    pointers.reserve(values.size() + 1);
    for (const auto& value : values) pointers.push_back(const_cast<char*>(value.c_str()));
    pointers.push_back(nullptr);
    return pointers;
}

int exit_code_of(int status) {
    if (WIFEXITED(status)) return WEXITSTATUS(status);
    if (WIFSIGNALED(status)) return 128 + WTERMSIG(status);
    return -1;
}

/// Accumulates bytes and emits complete lines, so a read() that splits a line
/// across two chunks does not produce two half-lines.
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

struct Child {
    pid_t pid = -1;
    int stdout_fd = -1;
    int stderr_fd = -1;
};

/// fork+exec with stdout and stderr redirected to fresh pipes.
Child start(const Command& command) {
    int out_pipe[2];
    int err_pipe[2];
    if (pipe(out_pipe) != 0) return {};
    if (pipe(err_pipe) != 0) {
        close(out_pipe[0]);
        close(out_pipe[1]);
        return {};
    }

    const auto env_strings = merged_environment(command.extra_env);
    auto envp = as_c_array(env_strings);
    auto argv = as_c_array(command.argv);
    const std::string working_dir = command.working_dir.string();

    const pid_t pid = fork();
    if (pid < 0) {
        for (int fd : {out_pipe[0], out_pipe[1], err_pipe[0], err_pipe[1]}) close(fd);
        return {};
    }
    if (pid == 0) {
        dup2(out_pipe[1], STDOUT_FILENO);
        dup2(err_pipe[1], STDERR_FILENO);
        for (int fd : {out_pipe[0], out_pipe[1], err_pipe[0], err_pipe[1]}) close(fd);
        if (!working_dir.empty() && chdir(working_dir.c_str()) != 0) _exit(126);
        environ = envp.data();
        execvp(argv[0], argv.data());
        _exit(127);
    }

    close(out_pipe[1]);
    close(err_pipe[1]);
    return {pid, out_pipe[0], err_pipe[0]};
}

/// Pump both pipes until they close, then reap. *on_tick* fires on poll timeout
/// and after every chunk so slow-but-alive children still tick.
int pump(Child child,
         const OutputSink& on_stdout,
         const OutputSink& on_stderr,
         const std::function<void()>& on_tick) {
    LineSplitter out_lines;
    LineSplitter err_lines;
    pollfd fds[2] = {{child.stdout_fd, POLLIN, 0}, {child.stderr_fd, POLLIN, 0}};
    bool open[2] = {true, true};

    while (open[0] || open[1]) {
        for (int i = 0; i < 2; ++i) fds[i].events = open[i] ? POLLIN : 0;
        const int ready = poll(fds, 2, 100);
        if (ready < 0 && errno != EINTR) break;
        if (on_tick) on_tick();
        if (ready <= 0) continue;

        for (int i = 0; i < 2; ++i) {
            if (!open[i] || (fds[i].revents & (POLLIN | POLLHUP | POLLERR)) == 0) continue;
            char buffer[4096];
            const ssize_t count = read(fds[i].fd, buffer, sizeof(buffer));
            if (count > 0) {
                (i == 0 ? out_lines : err_lines)
                    .feed(buffer, static_cast<size_t>(count), i == 0 ? on_stdout : on_stderr);
                continue;
            }
            if (count == 0 || (count < 0 && errno != EINTR && errno != EAGAIN)) {
                close(fds[i].fd);
                open[i] = false;
            }
        }
    }
    out_lines.flush(on_stdout);
    err_lines.flush(on_stderr);

    int status = 0;
    while (waitpid(child.pid, &status, 0) < 0 && errno == EINTR) {}
    return exit_code_of(status);
}

}  // namespace

int run(const Command& command, const OutputSink& on_line) {
    Child child = start(command);
    if (child.pid < 0) return -1;
    return pump(child, nullptr, on_line, nullptr);
}

int run_supervised(const Command& command,
                   const fs::path& log_file,
                   const OutputSink& on_stdout,
                   const OutputSink& on_stderr,
                   const std::function<void()>& on_tick) {
    Child child = start(command);
    if (child.pid < 0) return -1;

    std::ofstream log(log_file, std::ios::binary | std::ios::app);
    log << "$ ";
    for (const auto& arg : command.argv) log << arg << ' ';
    log << '\n' << std::flush;

    auto tee = [&log](const char* label, const std::string& line) {
        log << '[' << label << "] " << line << '\n' << std::flush;
    };

    return pump(
        child,
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
