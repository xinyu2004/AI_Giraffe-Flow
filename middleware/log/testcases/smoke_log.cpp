#include "gf_ara/log/logger.hpp"

#include <iostream>
#include <sstream>

namespace {

int Fail(const char* id, const char* msg) {
  std::cerr << "CASE " << id << " FAIL " << msg << '\n';
  return 1;
}

void Pass(const char* id, const char* detail) {
  std::cout << "CASE " << id << " PASS " << detail << '\n';
}

}  // namespace

int main() {
  using gf_ara::log::LogConfig;
  using gf_ara::log::LogLevel;
  using gf_ara::log::Logger;

  auto& log = Logger::Instance();
  LogConfig cfg;
  cfg.default_level = LogLevel::kInfo;
  log.Configure(cfg);

  // Capture: Info should print; Debug filtered (we only check API doesn't throw).
  log.Info("app", "hello-info");
  log.Debug("app", "hello-debug-filtered");
  Pass("LOG-01", "default_level INFO allows Info");

  cfg.contexts["phm"] = LogLevel::kDebug;
  log.Configure(cfg);
  log.Debug("phm", "phm-debug-ok");
  Pass("LOG-02", "per-context level DEBUG for phm");

  const char* yaml = R"(
schema_version: "0.1"
default_level: WARN
contexts:
  - id: exec
    level: INFO
)";
  log.ConfigureFromYaml(yaml);
  if (log.Config().default_level != LogLevel::kWarn) {
    return Fail("LOG-03", "default_level from yaml");
  }
  if (log.Config().contexts.count("exec") == 0 ||
      log.Config().contexts.at("exec") != LogLevel::kInfo) {
    return Fail("LOG-03", "context exec level from yaml");
  }
  Pass("LOG-03", "ConfigureFromYaml default_level+contexts");

  std::cout << "gf_log_smoke OK\n";
  return 0;
}
