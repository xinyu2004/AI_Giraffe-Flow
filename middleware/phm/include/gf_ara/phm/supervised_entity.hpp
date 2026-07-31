#pragma once

#include <gf/osal/clock.hpp>

#include <cstdint>
#include <string>
#include <string_view>

namespace gf_ara::phm {

enum class CheckpointStatus : std::uint8_t {
  kOk = 0,
  kAliveMissed,
  kDeadlineMissed,
  kLogicalFault,
};

/// Local Alive + Deadline + Logical supervision (ara::phm subset, in-process).
class SupervisedEntity {
 public:
  explicit SupervisedEntity(std::string_view name);

  void Configure(std::uint32_t alive_cycle_ms, std::uint32_t deadline_ms);
  void ReportAlive() noexcept;

  /// Logical health (M2). Default ok=true until ReportLogical(false).
  void ReportLogical(bool ok) noexcept;
  [[nodiscard]] bool LogicalOk() const noexcept { return logical_ok_; }

  /// True if last Alive is within deadline window (or never configured).
  [[nodiscard]] bool IsWithinDeadline() const noexcept;

  [[nodiscard]] CheckpointStatus Evaluate() const noexcept;
  [[nodiscard]] std::string_view Name() const noexcept { return name_; }

  /// Pause supervision during OTA / degraded mode (UCM/SM hook).
  void SetPaused(bool paused) noexcept;
  [[nodiscard]] bool Paused() const noexcept { return paused_; }

 private:
  std::string name_;
  std::uint32_t alive_cycle_ms_{0};
  std::uint32_t deadline_ms_{0};
  std::uint64_t last_alive_ns_{0};
  bool paused_{false};
  bool logical_ok_{true};
};

}  // namespace gf_ara::phm
