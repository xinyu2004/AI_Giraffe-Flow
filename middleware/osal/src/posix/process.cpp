#include "gf/osal/process.hpp"

#include <fcntl.h>
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>

#include <cerrno>
#include <cstring>
#include <vector>

namespace gf::osal {

ProcessId SpawnProcess(const ProcessSpawnRequest& req) {
  if (req.executable.empty()) {
    return kInvalidProcessId;
  }

  const pid_t pid = ::fork();
  if (pid < 0) {
    return kInvalidProcessId;
  }
  if (pid == 0) {
    if (!req.stdout_path.empty()) {
      const int flags =
          O_WRONLY | O_CREAT | (req.stdout_append ? O_APPEND : O_TRUNC);
      const int fd = ::open(req.stdout_path.c_str(), flags, 0644);
      if (fd >= 0) {
        ::dup2(fd, STDOUT_FILENO);
        ::dup2(fd, STDERR_FILENO);
        if (fd > STDERR_FILENO) {
          ::close(fd);
        }
      }
    }
    for (const auto& kv : req.env_set) {
      ::setenv(kv.first.c_str(), kv.second.c_str(), 1);
    }

    std::vector<char*> argv;
    argv.push_back(const_cast<char*>(req.executable.c_str()));
    for (const auto& a : req.args) {
      argv.push_back(const_cast<char*>(a.c_str()));
    }
    argv.push_back(nullptr);
    ::execv(req.executable.c_str(), argv.data());
    _exit(127);
  }
  return static_cast<ProcessId>(pid);
}

ProcessWaitResult WaitProcess(ProcessId id, bool nonblocking) {
  ProcessWaitResult out;
  if (!IsValidProcessId(id)) {
    out.status = ProcessWaitStatus::kError;
    return out;
  }
  int status = 0;
  const int flags = nonblocking ? WNOHANG : 0;
  const pid_t r = ::waitpid(static_cast<pid_t>(id), &status, flags);
  if (r == 0) {
    out.status = ProcessWaitStatus::kStillRunning;
    return out;
  }
  if (r < 0) {
    out.status = ProcessWaitStatus::kError;
    return out;
  }
  if (WIFEXITED(status)) {
    out.status = ProcessWaitStatus::kExited;
    out.exit_code = WEXITSTATUS(status);
    return out;
  }
  if (WIFSIGNALED(status)) {
    out.status = ProcessWaitStatus::kSignaled;
    out.term_signal = WTERMSIG(status);
    return out;
  }
  out.status = ProcessWaitStatus::kError;
  return out;
}

bool TerminateProcess(ProcessId id) {
  if (!IsValidProcessId(id)) {
    return false;
  }
  return ::kill(static_cast<pid_t>(id), SIGTERM) == 0;
}

bool KillProcess(ProcessId id) {
  if (!IsValidProcessId(id)) {
    return false;
  }
  return ::kill(static_cast<pid_t>(id), SIGKILL) == 0;
}

}  // namespace gf::osal
