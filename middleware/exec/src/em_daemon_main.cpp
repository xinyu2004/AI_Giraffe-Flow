#include "gf_ara/exec/em_daemon.hpp"

#include <gf_ara/log/logger.hpp>

#include <cstdint>
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
      << " --build-dir DIR [--platform DIR] [--log-dir DIR] [--deadline-ms N]\n"
      << "       (product: LoadFromDeployConfig / deploy_config.hpp)\n"
      << "   or: " << argv0
      << " --platform DIR --launch FILE --build-dir DIR  (YAML; smoke / GF_EM_USE_YAML=1)\n"
      << "Env: GF_PLATFORM_DIR GF_BUILD_DIR GF_EM_LOG_DIR GF_EM_LAUNCH GF_EM_USE_YAML\n";
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

bool FlagSet(int argc, char** argv, const char* flag) {
  for (int i = 1; i < argc; ++i) {
    if (std::strcmp(argv[i], flag) == 0) {
      return true;
    }
  }
  return false;
}

bool UseYaml(int argc, char** argv) {
  if (FlagSet(argc, argv, "--yaml") || FlagSet(argc, argv, "--use-yaml")) {
    return true;
  }
  for (int i = 1; i + 1 < argc; ++i) {
    if (std::strcmp(argv[i], "--launch") == 0) {
      return true;  // explicit CLI → smoke / opt-in YAML
    }
  }
  if (const char* v = std::getenv("GF_EM_USE_YAML"); v && v[0] == '1') {
    return true;
  }
  return false;
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

  if (build.empty()) {
    Usage(argv[0]);
    return 2;
  }

  const bool yaml_mode = UseYaml(argc, argv);
  if (yaml_mode && (platform.empty() || launch.empty())) {
    Usage(argv[0]);
    return 2;
  }

  const std::string logs = log_dir.empty() ? build + "/em_daemon_logs" : log_dir;
  {
    auto& log = gf_ara::log::Logger::Instance();
    if (!log.ConfigureFromGenerated() && !platform.empty()) {
      std::ifstream in(platform + "/log.yaml");
      if (in) {
        std::ostringstream ss;
        ss << in.rdbuf();
        log.ConfigureFromYaml(ss.str());
      }
    }
    if (std::getenv("GF_LOG_DIR") == nullptr || !*std::getenv("GF_LOG_DIR")) {
      ::setenv("GF_LOG_DIR", logs.c_str(), 0);
    }
    if (std::getenv("GF_LOG_FILE") == nullptr || !*std::getenv("GF_LOG_FILE")) {
      const std::string shared = logs + "/giraffe_modules.log";
      ::setenv("GF_LOG_FILE", shared.c_str(), 0);
    }
    log.ApplyEnvFileSink();
    if (yaml_mode) {
      log.Info("em", "gf_em_daemon start mode=yaml platform=" + platform +
                         " launch=" + launch + " build=" + build +
                         " log_dir=" + logs);
    } else {
      log.Info("em", "gf_em_daemon start mode=deploy_config platform=" + platform +
                         " build=" + build + " log_dir=" + logs);
    }
  }

  gf_ara::exec::EmDaemon em;
  const bool loaded = yaml_mode ? em.Load(platform, launch, build, logs)
                                : em.LoadFromDeployConfig(platform, build, logs);
  if (!loaded) {
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
