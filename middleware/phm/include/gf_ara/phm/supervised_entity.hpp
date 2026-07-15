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
};

/// Local Alive + Deadline supervision (ara::phm subset, in-process).
class SupervisedEntity {
 public:
  explicit SupervisedEntity(std::string_view name);

  void Configure(std::uint32_t alive_cycle_ms, std::uint32_t deadline_ms);
  void ReportAlive() noexcept;

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
};

}  // namespace gf_ara::phm
