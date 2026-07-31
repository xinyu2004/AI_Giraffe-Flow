#pragma once

#include "gf_ara/exec/execution_client.hpp"

#include <cstdint>
#include <string_view>

namespace gf_ara::exec {

/// In-process EM ledger (registry / client state / restart requests).
/// OS fork/exec lives in `EmDaemon` / `gf_em_daemon`.
class ExecutionManager {
 public:
  static void ResetForTest();

  static void RegisterProcess(std::string_view name);

  /// Desired state → Running (register if needed).
  static bool StartProcess(std::string_view name);

  static void OnClientOffer(std::string_view name);
  static void OnClientState(std::string_view name, ExecutionState state);

  /// PHM / health hook: request restart. Increments RestartCount; sets pending.
  static bool RequestRestart(std::string_view name, std::string_view reason);

  [[nodiscard]] static std::uint32_t RestartCount(std::string_view name) noexcept;
  [[nodiscard]] static bool RestartPending(std::string_view name) noexcept;
  static bool ConsumeRestartPending(std::string_view name);

  [[nodiscard]] static ExecutionState ReportedState(std::string_view name) noexcept;
  [[nodiscard]] static bool IsRegistered(std::string_view name) noexcept;
};

}  // namespace gf_ara::exec
