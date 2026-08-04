#include "gf_ara/ucm/ota_orchestrator.hpp"

#include <gf_ara/collector/event_collector.hpp>
#include <gf_ara/sm/state_client.hpp>

#include <cstdlib>
#include <mutex>

namespace gf_ara::ucm {
namespace {

std::mutex g_mu;
OtaConfig g_cfg{};
OtaOrchestrator::PauseHook g_pause;
std::atomic<float> g_progress{0.f};
std::string g_last_error;
PackageState g_last{PackageState::kIdle};

bool ForceFail(const PackageInfo& info) {
  if (const char* e = std::getenv("GF_UCM_FORCE_FAIL"); e && e[0] == '1') {
    return true;
  }
  return info.artifact_path.find("FORCE_FAIL") != std::string::npos;
}

void Pause(bool on) {
  if (g_pause) {
    g_pause(on);
  }
}

}  // namespace

void OtaOrchestrator::Configure(OtaConfig cfg) {
  std::lock_guard<std::mutex> lock(g_mu);
  g_cfg = std::move(cfg);
}

void OtaOrchestrator::SetPauseHook(PauseHook hook) {
  std::lock_guard<std::mutex> lock(g_mu);
  g_pause = std::move(hook);
}

void OtaOrchestrator::SetProgress(float p) { g_progress.store(p); }

float OtaOrchestrator::Progress() noexcept { return g_progress.load(); }

std::string OtaOrchestrator::LastError() {
  std::lock_guard<std::mutex> lock(g_mu);
  return g_last_error;
}

PackageState OtaOrchestrator::LastState() {
  std::lock_guard<std::mutex> lock(g_mu);
  return g_last;
}

void OtaOrchestrator::Fail(std::string_view reason) {
  {
    std::lock_guard<std::mutex> lock(g_mu);
    g_last_error = std::string(reason);
    g_last = PackageState::kFailed;
  }
  gf_ara::collector::EventCollector::Instance().ReportEvent(
      "ucm", "ota_failed", reason, gf_ara::collector::EventSeverity::kError);
}

gf_ara::core::Result<void> OtaOrchestrator::RunPackage(const PackageInfo& info) {
  OtaConfig cfg;
  PauseHook pause;
  {
    std::lock_guard<std::mutex> lock(g_mu);
    cfg = g_cfg;
    pause = g_pause;
    g_last_error.clear();
  }
  (void)pause;

  if (!cfg.enabled) {
    Fail("ucm disabled");
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }

  SetProgress(0.05f);
  if (!PackageManager::Initialize(cfg.manifest_path)) {
    Fail("Initialize failed");
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }

  const std::string fg = cfg.function_group.empty() ? "MachineFG" : cfg.function_group;
  gf_ara::sm::StateClient::EnsureGroup(fg, gf_ara::sm::FunctionGroupState::kRunning);
  if (!gf_ara::sm::StateClient::RequestTransition(fg, gf_ara::sm::FunctionGroupState::kUpdating)) {
    Fail("SM transition to Updating failed");
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kBusy);
  }
  Pause(true);
  SetProgress(0.15f);

  auto cleanup = [&](bool ok) {
    Pause(false);
    (void)gf_ara::sm::StateClient::RequestTransition(
        fg, gf_ara::sm::FunctionGroupState::kRunning);
    if (ok) {
      SetProgress(1.0f);
      std::lock_guard<std::mutex> lock(g_mu);
      g_last = PackageState::kActivated;
      g_last_error.clear();
    }
  };

  if (!PackageManager::StartTransfer(info)) {
    Fail("StartTransfer failed");
    if (cfg.allow_rollback) {
      (void)PackageManager::Rollback();
    }
    cleanup(false);
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kInvalidArgument);
  }
  SetProgress(0.40f);
  {
    std::lock_guard<std::mutex> lock(g_mu);
    g_last = PackageState::kTransferring;
  }

  if (ForceFail(info)) {
    Fail("forced failure (GF_UCM_FORCE_FAIL / FORCE_FAIL path)");
    if (cfg.allow_rollback) {
      (void)PackageManager::Rollback();
    }
    cleanup(false);
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }

  if (!PackageManager::ProcessSwPackage()) {
    Fail("ProcessSwPackage failed");
    if (cfg.allow_rollback) {
      (void)PackageManager::Rollback();
    }
    cleanup(false);
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  SetProgress(0.70f);
  {
    std::lock_guard<std::mutex> lock(g_mu);
    g_last = PackageManager::GetState();  // Present/Processing
  }

  // SoftwareCluster path: target "cluster:<name>" — EM stop/replace/start hook point (lite).
  if (info.target.rfind("cluster:", 0) == 0) {
    const auto& clusters = PackageManager::RuntimeConfig().clusters;
    const std::string cname = info.target.substr(8);
    bool found = false;
    for (const auto& c : clusters) {
      if (c.name == cname) {
        found = true;
        // Lite: record intent; real EM stop/start wired when exec exposes API.
        gf_ara::collector::EventCollector::Instance().ReportEvent(
            "ucm", "cluster_update", c.name + " procs=" + std::to_string(c.processes.size()),
            gf_ara::collector::EventSeverity::kInfo);
        break;
      }
    }
    if (!found && !cname.empty()) {
      gf_ara::collector::EventCollector::Instance().ReportEvent(
          "ucm", "cluster_update", "unknown cluster=" + cname,
          gf_ara::collector::EventSeverity::kWarn);
    }
  }

  if (!PackageManager::Activate()) {
    Fail("Activate failed");
    if (cfg.allow_rollback) {
      (void)PackageManager::Rollback();
    }
    cleanup(false);
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  SetProgress(0.90f);
  cleanup(true);
  gf_ara::collector::EventCollector::Instance().ReportEvent(
      "ucm", "ota_activated", info.id, gf_ara::collector::EventSeverity::kInfo);
  return gf_ara::core::Result<void>::Ok();
}

}  // namespace gf_ara::ucm
