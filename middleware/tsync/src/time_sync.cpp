#include "gf_ara/tsync/time_sync.hpp"

#include <gf/osal/clock.hpp>

namespace gf_ara::tsync {

TimeSyncProvider& TimeSyncProvider::Instance() {
  static TimeSyncProvider inst;
  return inst;
}

void TimeSyncProvider::Configure(TsyncConfig cfg) {
  cfg_ = cfg;
}

std::uint64_t TimeSyncProvider::NowNs() const {
  return gf::osal::MonotonicNowNs();
}

SyncStatus TimeSyncProvider::GetStatus() const noexcept {
  return cfg_.pretend_synchronized ? SyncStatus::kSynchronized : SyncStatus::kNotSynchronized;
}

}  // namespace gf_ara::tsync
