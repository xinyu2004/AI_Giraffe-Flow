#include "gf_ara/diag/doip.hpp"
#include "gf_ara/diag/doip_session.hpp"
#include "gf_ara/ucm/ota_orchestrator.hpp"
#include "gf_ara/collector/event_collector.hpp"

#include <atomic>
#include <chrono>
#include <cstdlib>
#include <iostream>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

namespace {

std::uint16_t EnvPort(const char* key, std::uint16_t def) {
  if (const char* e = std::getenv(key); e && *e) {
    return static_cast<std::uint16_t>(std::strtoul(e, nullptr, 10));
  }
  return def;
}

std::vector<std::uint8_t> HandleRoutine(const std::vector<std::uint8_t>& uds) {
  // 0x31 startRoutine (0x01) routineId 0xF100 — start OTA
  // payload: ASCII "id|artifact_path"
  if (uds.size() >= 4 && uds[0] == 0x31 && uds[1] == 0x01 && uds[2] == 0xF1 &&
      uds[3] == 0x00) {
    std::string spec(uds.begin() + 4, uds.end());
    gf_ara::ucm::PackageInfo info;
    const auto bar = spec.find('|');
    if (bar == std::string::npos) {
      info.id = spec.empty() ? "pkg.sil" : spec;
      info.artifact_path = "/tmp/gf_sil.swu";
    } else {
      info.id = spec.substr(0, bar);
      info.artifact_path = spec.substr(bar + 1);
    }
    info.version = "sil";
    const bool ok = static_cast<bool>(gf_ara::ucm::OtaOrchestrator::RunPackage(info));
    return {0x71, 0x01, 0xF1, 0x00, static_cast<std::uint8_t>(ok ? 0x00 : 0x01)};
  }
  // 0x31 requestResults (0x03) routineId 0xF101 — progress percent
  if (uds.size() >= 4 && uds[0] == 0x31 && uds[1] == 0x03 && uds[2] == 0xF1 &&
      uds[3] == 0x01) {
    const auto pct =
        static_cast<std::uint8_t>(gf_ara::ucm::OtaOrchestrator::Progress() * 100.f);
    return {0x71, 0x03, 0xF1, 0x01, pct};
  }
  return {0x7F, 0x31, 0x31};  // requestOutOfRange
}

}  // namespace

int main(int argc, char** argv) {
  (void)argc;
  (void)argv;

  gf_ara::collector::CollectorConfig ccfg;
  ccfg.forward = "local_store";
  ccfg.local_enabled = true;
  gf_ara::collector::EventCollector::Instance().Configure(ccfg);

  gf_ara::ucm::OtaConfig oc;
  oc.enabled = true;
  oc.allow_rollback = true;
  oc.function_group = "MachineFG";
  if (const char* m = std::getenv("GF_UCM_MANIFEST"); m && *m) {
    oc.manifest_path = m;
  }
  gf_ara::ucm::OtaOrchestrator::Configure(oc);

  gf_ara::diag::DoipConfig dcfg;
  dcfg.logical_address = "GF-ECU-SIL";
  dcfg.source_address = 0x0E00;
  dcfg.tcp_port = EnvPort("GF_DOIP_PORT", 13400);
  if (!gf_ara::diag::DoipStack::Initialize(dcfg)) {
    std::cerr << "DoipStack::Initialize failed\n";
    return EXIT_FAILURE;
  }

  gf_ara::diag::DoipTcpServer server;
  server.SetUdsHandler([](const std::vector<std::uint8_t>& uds) {
    return gf_ara::diag::DefaultUdsDispatch(uds, HandleRoutine);
  });

  gf_ara::diag::DoipSessionConfig scfg;
  scfg.listen_port = dcfg.tcp_port;
  scfg.entity_address = 0x0E00;
  auto port = server.Start(scfg);
  if (!port) {
    std::cerr << "DoipTcpServer::Start failed\n";
    return EXIT_FAILURE;
  }

  std::cout << "gf_doip_ota_server listening on TCP " << port.Value()
            << " (DoIP → UCM OTA)\n"
            << std::flush;

  // Stay up until SIGTERM / kill; smoke tests kill the process.
  while (server.Running()) {
    std::this_thread::sleep_for(std::chrono::milliseconds(200));
  }
  gf_ara::diag::DoipStack::Shutdown();
  return EXIT_SUCCESS;
}
