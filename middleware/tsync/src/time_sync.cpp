#include "gf_ara/tsync/time_sync.hpp"

#include <gf/osal/clock.hpp>

#include <cstdio>
#include <cstdlib>
#include <regex>
#include <string>

namespace gf_ara::tsync {

TimeSyncProvider& TimeSyncProvider::Instance() {
  static TimeSyncProvider inst;
  return inst;
}

void TimeSyncProvider::Configure(TsyncConfig cfg) {
  cfg_ = std::move(cfg);
  if (cfg_.backend == TsyncBackend::kOsalMonotonic) {
    cached_status_ =
        cfg_.pretend_synchronized ? SyncStatus::kSynchronized : SyncStatus::kNotSynchronized;
    cached_offset_ = cfg_.pretend_offset_ns;
  } else {
    RefreshLinuxPtp();
  }
}

void TimeSyncProvider::ConfigureFromYaml(std::string_view yaml_text) {
  TsyncConfig cfg;
  const std::string text(yaml_text);
  std::smatch m;
  if (std::regex_search(text, m, std::regex(R"(backend:\s*(\S+))"))) {
    const auto b = m[1].str();
    cfg.backend = (b == "linuxptp" || b == "gptp") ? TsyncBackend::kLinuxPtp
                                                   : TsyncBackend::kOsalMonotonic;
  }
  if (std::regex_search(text, m, std::regex(R"(pretend_synchronized:\s*(true|false))"))) {
    cfg.pretend_synchronized = (m[1].str() == "true");
  }
  Configure(cfg);
}

void TimeSyncProvider::RefreshLinuxPtp() const {
  // Best-effort: `pmc -u -b 0 'GET TIME_STATUS_NP'` when linuxptp installed.
  // No link dependency — popen only.
  cached_status_ = SyncStatus::kNotSynchronized;
  cached_offset_ = 0;
  cached_gm_.clear();
  const std::string cmd = cfg_.pmc_path + " -u -b 0 'GET TIME_STATUS_NP' 2>/dev/null";
  FILE* fp = ::popen(cmd.c_str(), "r");
  if (fp == nullptr) {
    // Fall back to pretend for SIL boards without pmc
    if (cfg_.pretend_synchronized) {
      cached_status_ = SyncStatus::kSynchronized;
      cached_offset_ = cfg_.pretend_offset_ns;
    }
    return;
  }
  char buf[512];
  std::string out;
  while (std::fgets(buf, sizeof(buf), fp) != nullptr) {
    out += buf;
  }
  ::pclose(fp);
  std::smatch m;
  if (std::regex_search(out, m, std::regex(R"(gmPresent\s+(\d+))"))) {
    if (m[1].str() != "0") {
      cached_status_ = SyncStatus::kSynchronized;
    }
  }
  if (std::regex_search(out, m, std::regex(R"(master_offset\s+(-?\d+))"))) {
    cached_offset_ = std::stoll(m[1].str());
  }
  if (cached_status_ == SyncStatus::kNotSynchronized && cfg_.pretend_synchronized && out.empty()) {
    cached_status_ = SyncStatus::kSynchronized;
    cached_offset_ = cfg_.pretend_offset_ns;
  }
}

std::uint64_t TimeSyncProvider::NowNs() const {
  const auto mono = gf::osal::MonotonicNowNs();
  if (cfg_.backend == TsyncBackend::kLinuxPtp) {
    RefreshLinuxPtp();
  }
  if (cached_status_ == SyncStatus::kSynchronized) {
    const auto adj = static_cast<std::int64_t>(mono) + cached_offset_;
    return adj < 0 ? 0ULL : static_cast<std::uint64_t>(adj);
  }
  return mono;
}

SyncStatus TimeSyncProvider::GetStatus() const noexcept {
  if (cfg_.backend == TsyncBackend::kLinuxPtp) {
    RefreshLinuxPtp();
  } else {
    cached_status_ =
        cfg_.pretend_synchronized ? SyncStatus::kSynchronized : SyncStatus::kNotSynchronized;
  }
  return cached_status_;
}

TsyncStatusDetail TimeSyncProvider::GetStatusDetail() const {
  (void)GetStatus();
  TsyncStatusDetail d;
  d.status = cached_status_;
  d.offset_ns = cached_offset_;
  d.gm_identity = cached_gm_;
  return d;
}

}  // namespace gf_ara::tsync
