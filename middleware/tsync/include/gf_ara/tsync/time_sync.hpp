#ifndef GF_ARA_TSYNC_TIME_SYNC_HPP
#define GF_ARA_TSYNC_TIME_SYNC_HPP

#include <cstdint>
#include <string_view>

namespace gf_ara::tsync {

enum class SyncStatus : std::uint8_t {
  kNotSynchronized = 0,
  kSynchronized,
};

struct TsyncConfig {
  bool pretend_synchronized{true};  // skeleton: no gPTP yet
};

/// Time sync skeleton. Now() delegates to OSAL monotonic; Status is stub.
class TimeSyncProvider {
 public:
  static TimeSyncProvider& Instance();

  void Configure(TsyncConfig cfg);
  [[nodiscard]] const TsyncConfig& Config() const noexcept { return cfg_; }

  [[nodiscard]] std::uint64_t NowNs() const;
  [[nodiscard]] SyncStatus GetStatus() const noexcept;

 private:
  TimeSyncProvider() = default;
  TsyncConfig cfg_{};
};

}  // namespace gf_ara::tsync

#endif
