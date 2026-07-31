#pragma once

#include <cstdint>
#include <string>
#include <utility>
#include <vector>

namespace gf::osal {

/// Portable process id (POSIX pid_t / QNX pid on backends).
using ProcessId = std::int64_t;
inline constexpr ProcessId kInvalidProcessId = -1;

struct ProcessSpawnRequest {
  std::string executable;                 // absolute path preferred
  std::vector<std::string> args;          // argv[1..] (argv[0] = executable basename ok)
  std::vector<std::pair<std::string, std::string>> env_set;  // overlay setenv
  std::string stdout_path;                // empty = inherit stdout/stderr
  bool stdout_append{false};              // false → truncate
};

enum class ProcessWaitStatus : std::uint8_t {
  kStillRunning = 0,
  kExited,
  kSignaled,
  kError,
};

struct ProcessWaitResult {
  ProcessWaitStatus status{ProcessWaitStatus::kStillRunning};
  int exit_code{-1};
  int term_signal{-1};
};

/// Create child process. Returns kInvalidProcessId on failure.
[[nodiscard]] ProcessId SpawnProcess(const ProcessSpawnRequest& req);

/// Wait for child. nonblocking=true → WNOHANG semantics.
[[nodiscard]] ProcessWaitResult WaitProcess(ProcessId id, bool nonblocking);

[[nodiscard]] bool TerminateProcess(ProcessId id);  // polite stop (SIGTERM)
[[nodiscard]] bool KillProcess(ProcessId id);         // force (SIGKILL)

[[nodiscard]] inline bool IsValidProcessId(ProcessId id) noexcept {
  return id != kInvalidProcessId && id > 0;
}

}  // namespace gf::osal
