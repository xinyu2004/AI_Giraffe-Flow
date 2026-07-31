#pragma once

// SIL helper: Offer→Running + SM FG + PHM Alive/Logical + Collector events.
// Env:
//   GF_PLATFORM_DIR     path to platform/ (or project root containing platform/)
//   GF_PHM_FAULT_MS     skip ReportAlive for N ms after first Alive (0=off)
//   GF_PHM_FAULT_INJECT_MS  alias of GF_PHM_FAULT_MS
//   GF_SM_ENTER_UPDATING_ON_FAULT  if 1, health_fault enters Updating (+ pause PHM)

#include "gf_ara/collector/event_collector.hpp"
#include "gf_ara/exec/execution_client.hpp"
#include "gf_ara/phm/supervised_entity.hpp"
#include "gf_ara/sm/state_client.hpp"

#include <chrono>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>

namespace gf::demo::platform_sil {

struct ExecProcessConfig {
  bool found{false};
  bool execution_client{true};
  std::string function_group;
};

struct PhmEntityConfig {
  bool found{false};
  std::string id;
  std::uint32_t alive_period_ms{100};
  std::uint32_t alive_timeout_ms{300};
  std::string on_failure{"log"};  // log | notify_sm
};

[[nodiscard]] std::string PlatformDir();

[[nodiscard]] ExecProcessConfig LoadExecProcess(std::string_view process_name);
[[nodiscard]] PhmEntityConfig LoadPhmEntity(std::string_view process_name);
void LoadCollectorConfig();

/// Offer + Running + SM Ensure; SupervisedEntity when phm.yaml lists process.
class ProcessSupervisor {
 public:
  bool Start(std::string_view process_name);
  void Tick();

  [[nodiscard]] bool HasPhm() const noexcept { return entity_.has_value(); }
  [[nodiscard]] gf_ara::phm::CheckpointStatus LastStatus() const noexcept {
    return last_status_;
  }
  [[nodiscard]] int MissCount() const noexcept { return miss_count_; }
  [[nodiscard]] int RecoverCount() const noexcept { return recover_count_; }

 private:
  void OnFault(gf_ara::phm::CheckpointStatus st);

  std::string process_;
  std::string function_group_{"MachineFG"};
  std::string on_failure_{"log"};
  std::optional<gf_ara::phm::SupervisedEntity> entity_;
  std::uint32_t alive_period_ms_{100};
  std::chrono::steady_clock::time_point next_alive_{};
  std::chrono::steady_clock::time_point fault_until_{};
  bool fault_pending_{false};
  bool fault_active_{false};
  bool ever_alive_{false};
  gf_ara::phm::CheckpointStatus last_status_{gf_ara::phm::CheckpointStatus::kOk};
  int miss_count_{0};
  int recover_count_{0};
};

}  // namespace gf::demo::platform_sil
