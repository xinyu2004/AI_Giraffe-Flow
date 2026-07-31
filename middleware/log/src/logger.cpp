#include "gf_ara/log/logger.hpp"

#include <cstdlib>
#include <iostream>
#include <regex>

namespace gf_ara::log {
namespace {

LogLevel EnvOverride(LogLevel fallback) {
  const char* v = std::getenv("GF_LOG_LEVEL");
  if (!v || !*v) {
    return fallback;
  }
  return Logger::ParseLevel(v, fallback);
}

}  // namespace

Logger& Logger::Instance() {
  static Logger inst;
  return inst;
}

const char* Logger::ToString(LogLevel level) noexcept {
  switch (level) {
    case LogLevel::kFatal:
      return "FATAL";
    case LogLevel::kError:
      return "ERROR";
    case LogLevel::kWarn:
      return "WARN";
    case LogLevel::kInfo:
      return "INFO";
    case LogLevel::kDebug:
      return "DEBUG";
    case LogLevel::kVerbose:
      return "VERBOSE";
  }
  return "INFO";
}

LogLevel Logger::ParseLevel(std::string_view s, LogLevel fallback) noexcept {
  if (s == "FATAL" || s == "fatal" || s == "Fatal") {
    return LogLevel::kFatal;
  }
  if (s == "ERROR" || s == "error" || s == "Error") {
    return LogLevel::kError;
  }
  if (s == "WARN" || s == "warn" || s == "Warn" || s == "WARNING") {
    return LogLevel::kWarn;
  }
  if (s == "INFO" || s == "info" || s == "Info") {
    return LogLevel::kInfo;
  }
  if (s == "DEBUG" || s == "debug" || s == "Debug") {
    return LogLevel::kDebug;
  }
  if (s == "VERBOSE" || s == "verbose" || s == "Verbose") {
    return LogLevel::kVerbose;
  }
  return fallback;
}

void Logger::Configure(LogConfig cfg) {
  std::lock_guard lock(mu_);
  cfg_ = std::move(cfg);
  cfg_.default_level = EnvOverride(cfg_.default_level);
}

void Logger::ConfigureFromYaml(std::string_view yaml_text) {
  LogConfig cfg;
  const std::string text(yaml_text);
  std::smatch m;
  if (std::regex_search(text, m, std::regex(R"(default_level:\s*(\S+))"))) {
    cfg.default_level = ParseLevel(m[1].str(), LogLevel::kInfo);
  }
  // contexts: - id: foo / level: DEBUG  (minimal scrape)
  std::regex ctx_re(R"(-?\s*id:\s*(\S+)[\s\S]*?level:\s*(\S+))");
  auto begin = std::sregex_iterator(text.begin(), text.end(), ctx_re);
  auto end = std::sregex_iterator();
  for (auto it = begin; it != end; ++it) {
    cfg.contexts[(*it)[1].str()] = ParseLevel((*it)[2].str(), cfg.default_level);
  }
  Configure(std::move(cfg));
}

LogLevel Logger::EffectiveLevel(std::string_view ctx) const {
  const auto it = cfg_.contexts.find(std::string(ctx));
  if (it != cfg_.contexts.end()) {
    return it->second;
  }
  return cfg_.default_level;
}

void Logger::Log(std::string_view ctx, LogLevel level, std::string_view msg) {
  std::lock_guard lock(mu_);
  if (static_cast<std::uint8_t>(level) > static_cast<std::uint8_t>(EffectiveLevel(ctx))) {
    return;
  }
  auto& out = (level <= LogLevel::kError) ? std::cerr : std::cout;
  out << "log: [" << ToString(level) << "] " << ctx << " " << msg << std::endl;
}

}  // namespace gf_ara::log
