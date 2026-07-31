#include "gf_ara/exec/em_daemon.hpp"

#include <cstdlib>
#include <cstring>
#include <iostream>
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

  gf_ara::exec::EmDaemon em;
  if (!em.Load(platform, launch, build, log_dir.empty() ? build + "/em_daemon_logs" : log_dir)) {
    return 1;
  }
  std::cout << "gf_em_daemon: processes=" << em.Config().processes.size()
            << " platform=" << platform << std::endl;
  if (!em.StartAll()) {
    return 1;
  }
  const int rc = em.RunForMs(deadline_ms);
  em.ShutdownAll();
  std::cout << "gf_em_daemon: exit rc=" << rc << std::endl;
  return rc;
}
