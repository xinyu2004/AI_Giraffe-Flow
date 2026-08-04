#include "gf_ara/log/logger.hpp"

#include <cstdlib>
#include <fstream>
#include <iostream>
#include <regex>
#include <unistd.h>

namespace gf_ara::log {
namespace {

LogLevel EnvOverride(LogLevel fallback) {
  const char* v = std::getenv("GF_LOG_LEVEL");
  if (!v || !*v) {
    return fallback;
  }
  return Logger::ParseLevel(v, fallback);
}

const char* Ansi(LogLevel level) {
  switch (level) {
    case LogLevel::kFatal:
    case LogLevel::kError:
      return "\033[31m";
    case LogLevel::kWarn:
      return "\033[33m";
    case LogLevel::kInfo:
      return "\033[32m";
    case LogLevel::kDebug:
      return "\033[36m";
    case LogLevel::kVerbose:
      return "\033[90m";
  }
  return "\033[0m";
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
  if (s == "FATAL" || s == "fatal") return LogLevel::kFatal;
  if (s == "ERROR" || s == "error") return LogLevel::kError;
  if (s == "WARN" || s == "warn" || s == "WARNING") return LogLevel::kWarn;
  if (s == "INFO" || s == "info") return LogLevel::kInfo;
  if (s == "DEBUG" || s == "debug") return LogLevel::kDebug;
  if (s == "VERBOSE" || s == "verbose") return LogLevel::kVerbose;
  return fallback;
}

void Logger::Configure(LogConfig cfg) {
  std::lock_guard lock(mu_);
  cfg_ = std::move(cfg);
  cfg_.default_level = EnvOverride(cfg_.default_level);
  if (cfg_.sinks.empty()) {
    cfg_.sinks = {"stdout", "stderr"};
  }
}

void Logger::ConfigureFromYaml(std::string_view yaml_text) {
  LogConfig cfg;
  const std::string text(yaml_text);
  std::smatch m;
  if (std::regex_search(text, m, std::regex(R"(default_level:\s*(\S+))"))) {
    cfg.default_level = ParseLevel(m[1].str(), LogLevel::kInfo);
  }
  if (std::regex_search(text, m, std::regex(R"(color:\s*(\S+))"))) {
    const auto c = m[1].str();
    if (c == "on" || c == "true") {
      cfg.color = ColorMode::kOn;
    } else if (c == "off" || c == "false") {
      cfg.color = ColorMode::kOff;
    } else {
      cfg.color = ColorMode::kAuto;
    }
  }
  if (std::regex_search(text, m, std::regex(R"(file_path:\s*(\S+))"))) {
    cfg.file_path = m[1].str();
  }
  std::regex sink_re(R"(sinks:\s*\[([^\]]*)\])");
  if (std::regex_search(text, m, sink_re)) {
    cfg.sinks.clear();
    std::regex tok(R"(([A-Za-z_]+))");
    const std::string inner = m[1].str();
    for (auto it = std::sregex_iterator(inner.begin(), inner.end(), tok);
         it != std::sregex_iterator(); ++it) {
      cfg.sinks.push_back((*it)[1].str());
    }
  }
  std::regex ctx_re(R"(-?\s*id:\s*(\S+)[\s\S]*?level:\s*(\S+))");
  for (auto it = std::sregex_iterator(text.begin(), text.end(), ctx_re);
       it != std::sregex_iterator(); ++it) {
    cfg.contexts[(*it)[1].str()] = ParseLevel((*it)[2].str(), cfg.default_level);
  }
  if (std::regex_search(text, m, std::regex(R"(gmt_export:[\s\S]*?enabled:\s*(true|false))"))) {
    cfg.gmt_export.enabled = (m[1].str() == "true");
  }
  if (std::regex_search(text, m, std::regex(R"(gmt_export:[\s\S]*?min_level:\s*(\S+))"))) {
    cfg.gmt_export.min_level = ParseLevel(m[1].str(), LogLevel::kError);
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

bool Logger::UseColor() const {
  if (cfg_.color == ColorMode::kOn) {
    return true;
  }
  if (cfg_.color == ColorMode::kOff) {
    return false;
  }
  return ::isatty(STDOUT_FILENO) != 0;
}

bool Logger::GmtAccepts(std::string_view ctx, LogLevel level) const {
  if (!cfg_.gmt_export.enabled) {
    return false;
  }
  if (static_cast<std::uint8_t>(level) > static_cast<std::uint8_t>(cfg_.gmt_export.min_level)) {
    return false;
  }
  if (cfg_.gmt_export.contexts.empty()) {
    return true;
  }
  for (const auto& c : cfg_.gmt_export.contexts) {
    if (c == ctx) {
      return true;
    }
  }
  return false;
}

void Logger::WriteFile(std::string_view line) {
  if (cfg_.file_path.empty()) {
    return;
  }
  std::ofstream out(cfg_.file_path, std::ios::app);
  if (out) {
    out << line << '\n';
  }
}

void Logger::Log(std::string_view ctx, LogLevel level, std::string_view msg) {
  std::lock_guard lock(mu_);
  if (static_cast<std::uint8_t>(level) > static_cast<std::uint8_t>(EffectiveLevel(ctx))) {
    return;
  }
  const std::string plain =
      std::string("log: [") + ToString(level) + "] " + std::string(ctx) + " " + std::string(msg);
  const bool color = UseColor();
  const bool to_err = level <= LogLevel::kError;
  for (const auto& sink : cfg_.sinks) {
    if (sink == "stderr" || (sink == "stdout" && !to_err) || (sink == "stdout" && to_err)) {
      // fall through unified below
    }
    if (sink == "file" || sink == "serial") {
      WriteFile(plain);
    }
  }
  auto& out = to_err ? std::cerr : std::cout;
  bool want_console = false;
  for (const auto& sink : cfg_.sinks) {
    if (sink == "stdout" || sink == "stderr" || sink == "serial") {
      want_console = true;
    }
  }
  if (want_console || cfg_.sinks.empty()) {
    if (color) {
      out << Ansi(level) << plain << "\033[0m" << std::endl;
    } else {
      out << plain << std::endl;
    }
  }
  if (GmtAccepts(ctx, level)) {
    if (gmt_bytes_ + plain.size() <= cfg_.gmt_export.max_bytes) {
      gmt_buf_.push_back(plain);
      gmt_bytes_ += static_cast<std::uint32_t>(plain.size());
    }
  }
}

std::vector<std::string> Logger::DrainGmtExport() {
  std::lock_guard lock(mu_);
  std::vector<std::string> out;
  out.swap(gmt_buf_);
  gmt_bytes_ = 0;
  return out;
}

}  // namespace gf_ara::log
