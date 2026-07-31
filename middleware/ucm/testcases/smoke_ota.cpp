#include "gf_ara/ucm/ota_orchestrator.hpp"
#include "gf_ara/collector/event_collector.hpp"
#include "gf_ara/sm/state_client.hpp"
#include "gf_ara/phm/supervised_entity.hpp"

#include <cstdlib>
#include <iostream>

namespace {

int Fail(const char* id, const char* msg) {
  std::cerr << "CASE " << id << " FAIL " << msg << '\n';
  return EXIT_FAILURE;
}

void Pass(const char* id, const char* detail) {
  std::cout << "CASE " << id << " PASS " << detail << '\n';
}

}  // namespace

int main() {
  unsetenv("GF_UCM_FORCE_FAIL");
  gf_ara::collector::EventCollector::Instance().Clear();

  bool paused = false;
  gf_ara::ucm::OtaOrchestrator::SetPauseHook([&](bool on) { paused = on; });
  gf_ara::ucm::OtaOrchestrator::Configure(gf_ara::ucm::OtaConfig{});

  gf_ara::ucm::PackageInfo ok;
  ok.id = "pkg.ok";
  ok.version = "1";
  ok.artifact_path = "/tmp/ok.swu";

  if (!gf_ara::ucm::OtaOrchestrator::RunPackage(ok)) {
    return Fail("UCM-OTA-01", "RunPackage success");
  }
  if (paused) {
    return Fail("UCM-OTA-01", "still paused");
  }
  if (gf_ara::sm::StateClient::GetState("MachineFG") !=
      gf_ara::sm::FunctionGroupState::kRunning) {
    return Fail("UCM-OTA-01", "SM not Running");
  }
  Pass("UCM-OTA-01", "success path unpause + Running");

  gf_ara::collector::EventCollector::Instance().Clear();
  setenv("GF_UCM_FORCE_FAIL", "1", 1);
  gf_ara::ucm::PackageInfo bad = ok;
  bad.id = "pkg.fail";
  bad.artifact_path = "/tmp/FORCE_FAIL.swu";
  if (gf_ara::ucm::OtaOrchestrator::RunPackage(bad)) {
    unsetenv("GF_UCM_FORCE_FAIL");
    return Fail("UCM-OTA-02", "expected fail");
  }
  unsetenv("GF_UCM_FORCE_FAIL");
  bool saw = false;
  for (const auto& e : gf_ara::collector::EventCollector::Instance().Snapshot()) {
    if (e.event_id == "ota_failed") {
      saw = true;
    }
  }
  if (!saw) {
    return Fail("UCM-OTA-02", "no collector event");
  }
  Pass("UCM-OTA-02", "fail → Collector ota_failed");

  // PHM pause API still works independently (documented hook)
  gf_ara::phm::SupervisedEntity se("ota_se");
  se.SetPaused(true);
  if (!se.Paused()) {
    return Fail("UCM-OTA-03", "SetPaused");
  }
  Pass("UCM-OTA-03", "PHM SetPaused available for OTA window");

  std::cout << "gf_ucm_ota_smoke OK\n";
  return EXIT_SUCCESS;
}
