#include "gf_ara/exec/em_daemon.hpp"

#include <gf_ara/log/logger.hpp>

#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>

namespace {

void Usage(const char* argv0) {
  std::cerr
      << "Usage: " << argv0
      << " --platform DIR --launch FILE --build-dir DIR [--log-dir DIR] [--deadline-ms N]\n"
      << "Env: GF_PLATFORM_DIR GF_EM_LAUNCH GF_BUILD_DIR GF_EM_LOG_DIR\n";
}

std::string OptOrEnv(int argc, char** argv, const char* flag, const char* env,
                     const char* fallback = "") {
  for (int i = 1; i + 1 < argc; ++i) {
    if (std::strcmp(argv[i], flag) == 0) {
      return argv[i + 1];
    }
  }
  if (const char* v = std::getenv(env); v && *v) {
    return v;
  }
  return fallback ? fallback : "";
}

}  // namespace

int main(int argc, char** argv) {
  for (int i = 1; i < argc; ++i) {
    if (std::strcmp(argv[i], "-h") == 0 || std::strcmp(argv[i], "--help") == 0) {
      Usage(argv[0]);
      return 0;
    }
  }

  const std::string platform = OptOrEnv(argc, argv, "--platform", "GF_PLATFORM_DIR");
  const std::string launch = OptOrEnv(argc, argv, "--launch", "GF_EM_LAUNCH");
  const std::string build = OptOrEnv(argc, argv, "--build-dir", "GF_BUILD_DIR");
  const std::string log_dir = OptOrEnv(argc, argv, "--log-dir", "GF_EM_LOG_DIR", "");
  std::uint32_t deadline_ms = 0;
  for (int i = 1; i + 1 < argc; ++i) {
    if (std::strcmp(argv[i], "--deadline-ms") == 0) {
      deadline_ms = static_cast<std::uint32_t>(std::strtoul(argv[i + 1], nullptr, 10));
    }
  }
  if (const char* d = std::getenv("GF_EM_DEADLINE_MS"); d && *d && deadline_ms == 0) {
    deadline_ms = static_cast<std::uint32_t>(std::strtoul(d, nullptr, 10));
  }

  if (platform.empty() || launch.empty() || build.empty()) {
    Usage(argv[0]);
    return 2;
  }

  const std::string logs = log_dir.empty() ? build + "/em_daemon_logs" : log_dir;
  {
    auto& log = gf_ara::log::Logger::Instance();
    std::ifstream in(platform + "/log.yaml");
    if (in) {
      std::ostringstream ss;
      ss << in.rdbuf();
      log.ConfigureFromYaml(ss.str());
    }
    if (std::getenv("GF_LOG_DIR") == nullptr || !*std::getenv("GF_LOG_DIR")) {
      ::setenv("GF_LOG_DIR", logs.c_str(), 0);
    }
    if (std::getenv("GF_LOG_FILE") == nullptr || !*std::getenv("GF_LOG_FILE")) {
      const std::string shared = logs + "/giraffe_modules.log";
      ::setenv("GF_LOG_FILE", shared.c_str(), 0);
    }
    log.ApplyEnvFileSink();
    log.Info("em", "gf_em_daemon start platform=" + platform + " launch=" + launch +
                       " build=" + build + " log_dir=" + logs);
  }

  gf_ara::exec::EmDaemon em;
  if (!em.Load(platform, launch, build, logs)) {
    gf_ara::log::Logger::Instance().Error("em", "Load failed");
    return 1;
  }
  if (!em.StartAll()) {
    gf_ara::log::Logger::Instance().Error("em", "StartAll failed");
    return 1;
  }
  gf_ara::log::Logger::Instance().Info("em", "polling children");
  const int rc = em.RunForMs(deadline_ms);
  em.ShutdownAll();
  gf_ara::log::Logger::Instance().Info("em", "exit rc=" + std::to_string(rc));
  return rc;
}
