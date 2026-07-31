#pragma once

#include "gf/osal/process.hpp"

#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace gf_ara::exec {

/// Child exit code meaning "EM please relaunch me" (sysexits EX_TEMPFAIL).
inline constexpr int kEmRestartExitCode = 75;

struct EmProcessSpec {
  std::string name;
  std::string binary;  // absolute, or relative to build_dir
  std::vector<std::string> args;
  std::vector<std::string> depends_on;
  bool restart_enabled{false};
  std::uint32_t max_restarts{3};
};

struct EmDaemonConfig {
  std::string platform_dir;
  std::string build_dir;
  std::string log_dir;
  std::vector<EmProcessSpec> processes;
};

/// OS-level Execution Management: OSAL Spawn/Wait + relaunch policy.
class EmDaemon {
 public:
  bool Configure(EmDaemonConfig cfg);
  /// Load exec.yaml (deps) + em_launch.yaml (binaries) + phm.yaml (restart flags).
  bool Load(std::string_view platform_dir, std::string_view launch_yaml,
            std::string_view build_dir, std::string_view log_dir);

  bool StartAll();
  /// Reap children; relaunch if policy allows. Returns false on fatal error.
  bool PollOnce();
  /// Run until all processes have finished (no pending relaunch), or deadline.
  int RunForMs(std::uint32_t deadline_ms);

  void RequestShutdown();
  void ShutdownAll();

  [[nodiscard]] std::uint32_t LaunchCount(std::string_view name) const noexcept;
  [[nodiscard]] std::uint32_t RestartCount(std::string_view name) const noexcept;
  [[nodiscard]] bool IsRunning(std::string_view name) const noexcept;
  [[nodiscard]] const EmDaemonConfig& Config() const noexcept { return cfg_; }

 private:
  struct Runtime {
    EmProcessSpec spec;
    gf::osal::ProcessId pid{gf::osal::kInvalidProcessId};
    std::uint32_t launches{0};
    std::uint32_t restarts{0};
    bool ever_started{false};
    bool terminal_exit{false};
  };

  bool Spawn(Runtime& rt, bool is_relaunch);
  static std::string ResolveBinary(const EmProcessSpec& spec, std::string_view build_dir);
  static bool TopoSort(std::vector<EmProcessSpec>& procs, std::string& err);

  EmDaemonConfig cfg_{};
  std::vector<Runtime> runtimes_;
  bool shutting_down_{false};
};

}  // namespace gf_ara::exec
