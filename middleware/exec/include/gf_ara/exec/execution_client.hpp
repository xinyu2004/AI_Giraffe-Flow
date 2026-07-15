#pragma once

#include <gf_ara/core/result.hpp>

#include <cstdint>
#include <string>
#include <string_view>

namespace gf_ara::exec {

enum class ExecutionState : std::uint8_t {
  kIdle = 0,
  kStarting,
  kRunning,
  kTerminating,
};

/// Minimal Process State Reporting facade (ara::exec subset).
class ExecutionClient {
 public:
  static gf_ara::core::Result<void> Offer(std::string_view process_name);
  static gf_ara::core::Result<void> ReportExecutionState(ExecutionState state);
  static ExecutionState GetState() noexcept;
  static std::string_view ProcessName() noexcept;
};

}  // namespace gf_ara::exec
