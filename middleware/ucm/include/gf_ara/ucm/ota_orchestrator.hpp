#ifndef GF_ARA_UCM_OTA_ORCHESTRATOR_HPP
#define GF_ARA_UCM_OTA_ORCHESTRATOR_HPP

#include <gf_ara/core/result.hpp>
#include <gf_ara/ucm/package_manager.hpp>

#include <atomic>
#include <functional>
#include <string>
#include <string_view>

namespace gf_ara::ucm {

struct OtaConfig {
  bool enabled{true};
  bool allow_rollback{true};
  std::string function_group{"MachineFG"};
  std::string manifest_path{"ucm://sil"};
};

/// Coordinates SM Updating + PHM pause hook + PackageManager + Collector events.
class OtaOrchestrator {
 public:
  using PauseHook = std::function<void(bool paused)>;

  static void Configure(OtaConfig cfg);
  static void SetPauseHook(PauseHook hook);

  /// Full sequence: SM→Updating → pause → Transfer→Process→Activate → unpause → Running.
  /// On failure: Collector event, optional Rollback, unpause, SM→Running, state=kFailed.
  /// Force fail: env `GF_UCM_FORCE_FAIL=1` or artifact_path containing "FORCE_FAIL".
  static gf_ara::core::Result<void> RunPackage(const PackageInfo& info);

  [[nodiscard]] static float Progress() noexcept;
  [[nodiscard]] static std::string LastError();
  [[nodiscard]] static PackageState LastState();

 private:
  static void SetProgress(float p);
  static void Fail(std::string_view reason);
};

}  // namespace gf_ara::ucm

#endif
