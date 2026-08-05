#include "gf_ara/log/logger.hpp"

#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>

namespace {

void Usage(const char* argv0) {
  std::cerr << "Usage: " << argv0
            << " [-a APP_ID] [-c CTX] [-l LEVEL] message...\n"
            << "  One-shot Info (default) into gf_ara::log DLT sink.\n"
            << "  Env: GF_DLT_APP_ID overrides -a if set after Configure.\n"
            << "  Sinks are dlt-only (Host/scripts already write console/file).\n";
}

}  // namespace

int main(int argc, char** argv) {
  std::string app_id = "HOST";
  std::string ctx = "host";
  auto level = gf_ara::log::LogLevel::kInfo;
  std::string msg;

  for (int i = 1; i < argc; ++i) {
    if (std::strcmp(argv[i], "-h") == 0 || std::strcmp(argv[i], "--help") == 0) {
      Usage(argv[0]);
      return 0;
    }
    if (std::strcmp(argv[i], "-a") == 0 && i + 1 < argc) {
      app_id = argv[++i];
      continue;
    }
    if (std::strcmp(argv[i], "-c") == 0 && i + 1 < argc) {
      ctx = argv[++i];
      continue;
    }
    if (std::strcmp(argv[i], "-l") == 0 && i + 1 < argc) {
      level = gf_ara::log::Logger::ParseLevel(argv[++i], gf_ara::log::LogLevel::kInfo);
      continue;
    }
    if (!msg.empty()) {
      msg.push_back(' ');
    }
    msg += argv[i];
  }
  if (msg.empty()) {
    Usage(argv[0]);
    return 2;
  }

  ::setenv("GF_DLT_APP_ID", app_id.c_str(), 1);

  gf_ara::log::LogConfig cfg;
  cfg.default_level = gf_ara::log::LogLevel::kVerbose;
  cfg.color = gf_ara::log::ColorMode::kOff;
  cfg.sinks = {"dlt"};
  cfg.dlt_app_id = app_id;
  auto& log = gf_ara::log::Logger::Instance();
  log.Configure(std::move(cfg));
  log.Log(ctx, level, msg);
  return 0;
}
