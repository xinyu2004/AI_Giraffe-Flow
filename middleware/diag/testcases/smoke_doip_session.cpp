#include "gf_ara/diag/doip_session.hpp"
#include "gf_ara/diag/uds_dispatcher.hpp"
#include "gf_ara/ucm/ota_orchestrator.hpp"
#include "gf_ara/collector/event_collector.hpp"
#include "gf_ara/sm/state_client.hpp"

#include <chrono>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

namespace {

int Fail(const char* id, const char* msg) {
  std::cerr << "CASE " << id << " FAIL " << msg << '\n';
  return EXIT_FAILURE;
}

void Pass(const char* id, const char* detail) {
  std::cout << "CASE " << id << " PASS " << detail << '\n';
}

std::vector<std::uint8_t> OtaRoutine(const std::vector<std::uint8_t>& uds) {
  if (uds.size() >= 4 && uds[0] == 0x31 && uds[1] == 0x01 && uds[2] == 0xF1 &&
      uds[3] == 0x00) {
    std::string spec(uds.begin() + 4, uds.end());
    gf_ara::ucm::PackageInfo info;
    const auto bar = spec.find('|');
    if (bar == std::string::npos) {
      info.id = "pkg";
      info.artifact_path = spec;
    } else {
      info.id = spec.substr(0, bar);
      info.artifact_path = spec.substr(bar + 1);
    }
    // Semver required: non-numeric versions parse as 0 and trip anti-downgrade
    // against leftover PER (e.g. gf_ucm_package_manager_smoke → VER:pkg.demo=1.0.0).
    info.version = "2.0.0";
    const bool ok = static_cast<bool>(gf_ara::ucm::OtaOrchestrator::RunPackage(info));
    return {0x71, 0x01, 0xF1, 0x00, static_cast<std::uint8_t>(ok ? 0x00 : 0x01)};
  }
  return {0x7F, 0x31, 0x31};
}

}  // namespace

int main() {
  unsetenv("GF_UCM_FORCE_FAIL");

  gf_ara::collector::EventCollector::Instance().Clear();
  gf_ara::collector::CollectorConfig ccfg;
  ccfg.local_enabled = true;
  gf_ara::collector::EventCollector::Instance().Configure(ccfg);

  gf_ara::ucm::OtaOrchestrator::Configure(gf_ara::ucm::OtaConfig{});

  gf_ara::diag::UdsConfig ucfg;
  ucfg.iso_14229_uds = true;
  ucfg.iso_13400_doip = true;
  gf_ara::diag::UdsDispatcher::Instance().Configure(ucfg);
  gf_ara::diag::UdsDispatcher::Instance().SetRoutineHook(OtaRoutine);

  gf_ara::diag::DoipTcpServer server;
  server.SetUdsHandler([](const std::vector<std::uint8_t>& uds) {
    return gf_ara::diag::UdsDispatcher::Instance().Handle(uds);
  });

  gf_ara::diag::DoipSessionConfig scfg;
  scfg.listen_port = 0;
  auto port = server.Start(scfg);
  if (!port) {
    return Fail("DOIP-S01", "server Start");
  }
  Pass("DOIP-S01", "TCP listen");

  std::this_thread::sleep_for(std::chrono::milliseconds(50));

  gf_ara::diag::DoipTcpClient client;
  if (!client.Connect("127.0.0.1", port.Value())) {
    return Fail("DOIP-S02", "Connect");
  }
  if (!client.RoutingActivation()) {
    return Fail("DOIP-S02", "RoutingActivation");
  }
  Pass("DOIP-S02", "RoutingActivation over TCP");

  auto tp = client.Transceive({0x3E, 0x00});
  if (!tp || tp.Value().empty() || tp.Value()[0] != 0x7E) {
    return Fail("DOIP-S03", "TesterPresent");
  }
  Pass("DOIP-S03", "TesterPresent over TCP");

  // Distinct id from package_manager smoke (pkg.demo) to avoid PER version crosstalk.
  std::string payload = "pkg.doip.session|/tmp/gf_ok.swu";
  {
    std::ofstream f("/tmp/gf_ok.swu", std::ios::binary | std::ios::trunc);
    f.write("GFSW", 4);
    f.write("\x01\x00ok", 5);
  }
  std::vector<std::uint8_t> uds = {0x31, 0x01, 0xF1, 0x00};
  uds.insert(uds.end(), payload.begin(), payload.end());
  auto ota = client.Transceive(uds);
  if (!ota || ota.Value().size() < 5 || ota.Value()[0] != 0x71 || ota.Value()[4] != 0x00) {
    return Fail("DOIP-S04", "OTA startRoutine success");
  }
  if (gf_ara::sm::StateClient::GetState("MachineFG") !=
      gf_ara::sm::FunctionGroupState::kRunning) {
    return Fail("DOIP-S04", "SM back to Running");
  }
  Pass("DOIP-S04", "OTA success + SM Running");

  gf_ara::collector::EventCollector::Instance().Clear();
  setenv("GF_UCM_FORCE_FAIL", "1", 1);
  std::string bad = "pkg.doip.session.bad|/tmp/FORCE_FAIL.swu";
  std::vector<std::uint8_t> uds2 = {0x31, 0x01, 0xF1, 0x00};
  uds2.insert(uds2.end(), bad.begin(), bad.end());
  auto fail = client.Transceive(uds2);
  unsetenv("GF_UCM_FORCE_FAIL");
  if (!fail || fail.Value().size() < 5 || fail.Value()[4] != 0x01) {
    return Fail("DOIP-S05", "OTA forced fail status");
  }
  bool saw = false;
  for (const auto& e : gf_ara::collector::EventCollector::Instance().Snapshot()) {
    if (e.source == "ucm" && e.event_id == "ota_failed") {
      saw = true;
      break;
    }
  }
  if (!saw) {
    return Fail("DOIP-S05", "Collector ota_failed");
  }
  Pass("DOIP-S05", "OTA fail → Collector");

  client.Close();
  server.Stop();
  std::cout << "gf_doip_session_smoke OK\n";
  return EXIT_SUCCESS;
}
