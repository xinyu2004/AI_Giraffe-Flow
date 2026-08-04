#ifndef GF_ARA_TSYNC_TIME_SYNC_HPP
#define GF_ARA_TSYNC_TIME_SYNC_HPP

#include <cstdint>
#include <string>
#include <string_view>

namespace gf_ara::tsync {

enum class SyncStatus : std::uint8_t {
  kNotSynchronized = 0,
  kSynchronized,
};

enum class TsyncBackend : std::uint8_t {
  kOsalMonotonic = 0,
  kLinuxPtp = 1,  // read pmc/ptp status; falls back if unavailable
};

struct TsyncConfig {
  TsyncBackend backend{TsyncBackend::kOsalMonotonic};
  bool pretend_synchronized{true};  // SIL / osal backend
  std::int64_t pretend_offset_ns{0};
  std::string pmc_path{"pmc"};  // optional external tool
};

struct TsyncStatusDetail {
  SyncStatus status{SyncStatus::kNotSynchronized};
  std::int64_t offset_ns{0};
  std::string gm_identity;
};

/// gf_ara::tsync lite — gPTP via linuxptp on board; osal/mock on SIL.
class TimeSyncProvider {
 public:
  static TimeSyncProvider& Instance();

  void Configure(TsyncConfig cfg);
  void ConfigureFromYaml(std::string_view yaml_text);
  [[nodiscard]] const TsyncConfig& Config() const noexcept { return cfg_; }

  [[nodiscard]] std::uint64_t NowNs() const;
  [[nodiscard]] SyncStatus GetStatus() const noexcept;
  [[nodiscard]] TsyncStatusDetail GetStatusDetail() const;

 private:
  TimeSyncProvider() = default;
  void RefreshLinuxPtp() const;

  TsyncConfig cfg_{};
  mutable SyncStatus cached_status_{SyncStatus::kNotSynchronized};
  mutable std::int64_t cached_offset_{0};
  mutable std::string cached_gm_;
};

}  // namespace gf_ara::tsync

#endif
