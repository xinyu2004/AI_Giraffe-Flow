#include "gf_ara/diag/doip.hpp"
#include "gf_ara/diag/doip_session.hpp"
#include "gf_ara/diag/uds_dispatcher.hpp"
#include "gf_ara/ucm/ota_orchestrator.hpp"
#include "gf_ara/ucm/package_manager.hpp"
#include "gf_ara/collector/event_collector.hpp"
#include "gf_ara/log/logger.hpp"

#include <chrono>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <regex>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

namespace {

std::string ReadFile(const std::string& path) {
  std::ifstream in(path);
  if (!in) {
    return {};
  }
  std::ostringstream ss;
  ss << in.rdbuf();
  return ss.str();
}

std::string PlatformPath(const char* name) {
  const char* dir = std::getenv("GF_PLATFORM_DIR");
  if (dir == nullptr || dir[0] == '\0') {
    return {};
  }
  return std::string(dir) + "/" + name;
}

std::uint16_t EnvU16(const char* key, std::uint16_t def) {
  if (const char* e = std::getenv(key); e && *e) {
    return static_cast<std::uint16_t>(std::strtoul(e, nullptr, 0));
  }
  return def;
}

std::uint32_t EnvU32(const char* key, std::uint32_t def) {
  if (const char* e = std::getenv(key); e && *e) {
    return static_cast<std::uint32_t>(std::strtoul(e, nullptr, 10));
  }
  return def;
}

bool EnvBool(const char* key, bool def) {
  if (const char* e = std::getenv(key); e && *e) {
    return !(e[0] == '0' || e[0] == 'n' || e[0] == 'N' || e[0] == 'f' || e[0] == 'F');
  }
  return def;
}

std::vector<std::uint8_t> OtaRoutine(const std::vector<std::uint8_t>& uds) {
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
    // Numeric semver — non-numeric ("sil") parses as 0 and fails anti-downgrade vs PER.
    info.version = "1.0.0";
    const bool ok = static_cast<bool>(gf_ara::ucm::OtaOrchestrator::RunPackage(info));
    return {0x71, 0x01, 0xF1, 0x00, static_cast<std::uint8_t>(ok ? 0x00 : 0x01)};
  }
  if (uds.size() >= 4 && uds[0] == 0x31 && uds[1] == 0x03 && uds[2] == 0xF1 &&
      uds[3] == 0x01) {
    const auto pct =
        static_cast<std::uint8_t>(gf_ara::ucm::OtaOrchestrator::Progress() * 100.f);
    return {0x71, 0x03, 0xF1, 0x01, pct};
  }
  return {0x7F, 0x31, 0x31};
}

}  // namespace

int main() {
  gf_ara::collector::CollectorConfig ccfg;
  ccfg.forward = "local_store";
  ccfg.local_enabled = true;
  const auto collector_yaml = ReadFile(PlatformPath("collector.yaml"));
  if (!collector_yaml.empty()) {
    gf_ara::collector::EventCollector::Instance().ConfigureFromYaml(collector_yaml);
  } else {
    gf_ara::collector::EventCollector::Instance().Configure(ccfg);
  }
  // DEM DTCs come from apps via shared GF_PER_DIR (PHM → ReportEvent → PersistDtc).
  // 0x19 reloads with EventCollector::ReloadDtcsFromPer — no in-process seed.

  gf_ara::ucm::OtaConfig oc;
  oc.enabled = true;
  oc.allow_rollback = true;
  oc.function_group = "MachineFG";
  gf_ara::ucm::UcmRuntimeConfig ur;
  ur.enabled = true;
  ur.allow_rollback = true;
  ur.function_group = "MachineFG";
  const auto ucm_yaml = ReadFile(PlatformPath("ucm.yaml"));
  if (!ucm_yaml.empty()) {
    std::smatch m;
    if (std::regex_search(ucm_yaml, m, std::regex(R"(enabled:\s*(true|false))"))) {
      ur.enabled = oc.enabled = (m[1].str() == "true");
    }
    if (std::regex_search(ucm_yaml, m, std::regex(R"(allow_rollback:\s*(true|false))"))) {
      ur.allow_rollback = oc.allow_rollback = (m[1].str() == "true");
    }
    if (std::regex_search(ucm_yaml, m, std::regex(R"(function_group:\s*(\S+))"))) {
      ur.function_group = oc.function_group = m[1].str();
    }
    if (std::regex_search(ucm_yaml, m, std::regex(R"(package_source:\s*(\S+))"))) {
      ur.package_source = m[1].str();
    }
  }
  if (const char* m = std::getenv("GF_UCM_MANIFEST"); m && *m) {
    oc.manifest_path = m;
    ur.manifest_path = m;
  }
  gf_ara::ucm::PackageManager::SetRuntimeConfig(ur);
  gf_ara::ucm::OtaOrchestrator::Configure(oc);

  gf_ara::diag::UdsConfig ucfg;
  ucfg.iso_14229_uds = true;
  ucfg.iso_13400_doip = true;
  if (const char* p = std::getenv("GF_DIAG_SEC_PLUGIN"); p && *p) {
    ucfg.security_plugin_path = p;
  }
  ucfg.s3_server_ms = EnvU32("GF_DIAG_S3_SERVER_MS", 5000);
  ucfg.tester_present_period_ms = EnvU32("GF_DIAG_TP_PERIOD_MS", 2000);
  ucfg.p2_server_ms = EnvU32("GF_DIAG_P2_SERVER_MS", 50);
  ucfg.p2_star_server_ms = EnvU32("GF_DIAG_P2STAR_SERVER_MS", 5000);
  ucfg.security_delay_ms = EnvU32("GF_DIAG_SECURITY_DELAY_MS", 10000);
  if (const char* m = std::getenv("GF_OTA_TRANSFER_MODE"); m && *m) {
    ucfg.ota_mode = gf_ara::diag::UdsDispatcher::ParseOtaMode(m);
  } else {
    ucfg.ota_mode = gf_ara::diag::OtaTransferMode::kRequestFileTransfer;
  }
  ucfg.ota_require_programming_session = EnvBool("GF_OTA_REQUIRE_PROG_SESSION", true);
  ucfg.ota_require_security = EnvBool("GF_OTA_REQUIRE_SECURITY", true);
  ucfg.ota_max_block_length = EnvU32("GF_OTA_MAX_BLOCK", 1024);

  if (!gf_ara::diag::UdsDispatcher::StandardsValid(ucfg.iso_14229_uds, ucfg.iso_13400_doip)) {
    std::cerr << "invalid standards: 13400 requires 14229\n";
    return EXIT_FAILURE;
  }
  gf_ara::diag::UdsDispatcher::Instance().Configure(ucfg);
  // Optional DID seed from diag.yaml (id: 0xF191 style lines)
  const auto diag_yaml = ReadFile(PlatformPath("diag.yaml"));
  if (!diag_yaml.empty()) {
    std::regex did_re(R"(-?\s*id:\s*(0x[0-9A-Fa-f]+|\d+)[\s\S]*?name:\s*(\S+))");
    for (auto it = std::sregex_iterator(diag_yaml.begin(), diag_yaml.end(), did_re);
         it != std::sregex_iterator(); ++it) {
      const auto did = static_cast<std::uint16_t>(std::stoul((*it)[1].str(), nullptr, 0));
      const std::string name = (*it)[2].str();
      gf_ara::diag::UdsDispatcher::Instance().SetDid(
          did, std::vector<std::uint8_t>(name.begin(), name.end()));
    }
  }
  // Version DID 0xF191 from UCM stored version when present
  {
    const auto ver = gf_ara::ucm::PackageManager::StoredVersion("pkg.xfer");
    const std::string v = ver.empty() ? std::string("sil") : ver;
    gf_ara::diag::UdsDispatcher::Instance().SetDid(
        0xF191, std::vector<std::uint8_t>(v.begin(), v.end()));
  }
  gf_ara::diag::UdsDispatcher::Instance().SetRoutineHook(OtaRoutine);
  gf_ara::diag::UdsDispatcher::Instance().SetTransferCompleteHook(
      [](const std::string& path, std::uint64_t bytes) {
        gf_ara::ucm::PackageInfo info;
        info.id = "pkg.xfer";
        info.artifact_path = path;
        // Monotonic-ish semver from transfer size (must stay numeric for CompareVersion).
        info.version = "1." + std::to_string(bytes / 1000) + "." + std::to_string(bytes % 1000);
        return static_cast<bool>(gf_ara::ucm::OtaOrchestrator::RunPackage(info));
      });

  gf_ara::diag::DoipConfig dcfg;
  dcfg.logical_address = "GF-ECU-SIL";
  dcfg.source_address = EnvU16("GF_DOIP_LOGICAL_ADDR", 0x0E00);
  dcfg.tcp_port = EnvU16("GF_DOIP_PORT", 13400);
  if (!gf_ara::diag::DoipStack::Initialize(dcfg)) {
    std::cerr << "DoipStack::Initialize failed\n";
    return EXIT_FAILURE;
  }

  gf_ara::diag::DoipTcpServer server;
  server.SetUdsHandler([](const std::vector<std::uint8_t>& uds) {
    return gf_ara::diag::UdsDispatcher::Instance().Handle(uds);
  });

  gf_ara::diag::DoipSessionConfig scfg;
  scfg.listen_port = dcfg.tcp_port;
  scfg.entity_address = dcfg.source_address;
  scfg.expected_tester = EnvU16("GF_DOIP_TESTER_ADDR", 0x0E80);
  auto port = server.Start(scfg);
  if (!port) {
    std::cerr << "DoipTcpServer::Start failed\n";
    return EXIT_FAILURE;
  }

  const char* mode_name = "request_file_transfer";
  if (ucfg.ota_mode == gf_ara::diag::OtaTransferMode::kRequestDownload) {
    mode_name = "request_download";
  } else if (ucfg.ota_mode == gf_ara::diag::OtaTransferMode::kRoutineSil) {
    mode_name = "routine_sil";
  }

  std::cout << "gf_doip_ota_server listening on TCP " << port.Value()
            << " (DoIP→UDS→UCM; mode=" << mode_name
            << "; S3=" << ucfg.s3_server_ms << "ms"
            << "; TP_period=" << ucfg.tester_present_period_ms << "ms)\n"
            << std::flush;

  while (server.Running()) {
    gf_ara::diag::UdsDispatcher::Instance().TickTimeouts();
    std::this_thread::sleep_for(std::chrono::milliseconds(200));
  }
  gf_ara::diag::DoipStack::Shutdown();
  return EXIT_SUCCESS;
}
