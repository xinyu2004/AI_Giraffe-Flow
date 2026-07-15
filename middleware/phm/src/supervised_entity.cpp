#include "gf_ara/phm/supervised_entity.hpp"

namespace gf_ara::phm {

SupervisedEntity::SupervisedEntity(std::string_view name)
    : name_(name.begin(), name.end()) {}

void SupervisedEntity::Configure(std::uint32_t alive_cycle_ms, std::uint32_t deadline_ms) {
  alive_cycle_ms_ = alive_cycle_ms;
  deadline_ms_ = deadline_ms == 0 ? alive_cycle_ms : deadline_ms;
  last_alive_ns_ = 0;
}

void SupervisedEntity::ReportAlive() noexcept {
  last_alive_ns_ = gf::osal::MonotonicNowNs();
}

bool SupervisedEntity::IsWithinDeadline() const noexcept {
  if (paused_ || deadline_ms_ == 0) {
    return true;
  }
  if (last_alive_ns_ == 0) {
    return false;
  }
  const auto now = gf::osal::MonotonicNowNs();
  const auto limit = static_cast<std::uint64_t>(deadline_ms_) * 1000000ull;
  return (now - last_alive_ns_) <= limit;
}

CheckpointStatus SupervisedEntity::Evaluate() const noexcept {
  if (paused_) {
    return CheckpointStatus::kOk;
  }
  if (deadline_ms_ == 0) {
    return CheckpointStatus::kOk;
  }
  if (last_alive_ns_ == 0) {
    return CheckpointStatus::kAliveMissed;
  }
  if (!IsWithinDeadline()) {
    return CheckpointStatus::kDeadlineMissed;
  }
  return CheckpointStatus::kOk;
}

void SupervisedEntity::SetPaused(bool paused) noexcept { paused_ = paused; }

}  // namespace gf_ara::phm
