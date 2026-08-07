#include "gf_ara/log/logger.hpp"

#include "gf_ara/log/dlt_sink.hpp"

#if defined(GF_HAS_LOG_CONFIG) && GF_HAS_LOG_CONFIG
#include <gf_gen/log_config.hpp>
#endif

#include <cstdlib>
#include <filesystem>
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
  if (const char* app = std::getenv("GF_DLT_APP_ID"); app != nullptr && app[0] != '\0') {
    cfg_.dlt_app_id = app;
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
  if (std::regex_search(text, m, std::regex(R"(file_max_bytes:\s*(\d+))"))) {
    cfg.file_max_bytes = static_cast<std::uint32_t>(std::stoul(m[1].str()));
  }
  if (std::regex_search(text, m, std::regex(R"(dlt:\s*[\s\S]*?app_id:\s*(\S+))"))) {
    cfg.dlt_app_id = m[1].str();
  } else if (std::regex_search(text, m, std::regex(R"(dlt_app_id:\s*(\S+))"))) {
    cfg.dlt_app_id = m[1].str();
  }
  if (std::regex_search(text, m, std::regex(R"(dlt:\s*[\s\S]*?max_contexts:\s*(\d+))"))) {
    cfg.dlt_max_contexts = static_cast<std::uint32_t>(std::stoul(m[1].str()));
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
  } else if (std::regex_search(text, m, std::regex(R"(sinks:\s*\n((?:\s*-\s*\S+\s*\n?)+))"))) {
    cfg.sinks.clear();
    const std::string block = m[1].str();
    std::regex tok(R"(-\s*([A-Za-z_]+))");
    for (auto it = std::sregex_iterator(block.begin(), block.end(), tok);
         it != std::sregex_iterator(); ++it) {
      cfg.sinks.push_back((*it)[1].str());
    }
  }
  std::regex ctx_re(R"(-?\s*id:\s*(\S+)[\s\S]*?level:\s*(\S+))");
  for (auto it = std::sregex_iterator(text.begin(), text.end(), ctx_re);
       it != std::sregex_iterator(); ++it) {
    cfg.contexts[(*it)[1].str()] = ParseLevel((*it)[2].str(), cfg.default_level);
  }
  Configure(std::move(cfg));
}

bool Logger::ConfigureFromGenerated() {
#if defined(GF_HAS_LOG_CONFIG) && GF_HAS_LOG_CONFIG
  LogConfig cfg;
  cfg.default_level = ParseLevel(gf_gen::log::kDefaultLevel, LogLevel::kInfo);
  const std::string color = gf_gen::log::kColor ? gf_gen::log::kColor : "auto";
  if (color == "on") {
    cfg.color = ColorMode::kOn;
  } else if (color == "off") {
    cfg.color = ColorMode::kOff;
  } else {
    cfg.color = ColorMode::kAuto;
  }
  cfg.sinks.clear();
  for (std::size_t i = 0; i < gf_gen::log::kSinkCount; ++i) {
    if (gf_gen::log::kSinks[i] != nullptr) {
      cfg.sinks.emplace_back(gf_gen::log::kSinks[i]);
    }
  }
  if (cfg.sinks.empty()) {
    cfg.sinks = {"stdout", "stderr"};
  }
  if (gf_gen::log::kFilePath != nullptr) {
    cfg.file_path = gf_gen::log::kFilePath;
  }
  cfg.file_max_bytes = gf_gen::log::kFileMaxBytes;
  if (gf_gen::log::kDltAppId != nullptr) {
    cfg.dlt_app_id = gf_gen::log::kDltAppId;
  }
  cfg.dlt_max_contexts = gf_gen::log::kDltMaxContexts;
  for (std::size_t i = 0; i < gf_gen::log::kContextCount; ++i) {
    const auto& c = gf_gen::log::kContexts[i];
    if (c.id == nullptr || !*c.id) {
      continue;
    }
    cfg.contexts[c.id] = ParseLevel(c.level ? c.level : "INFO", cfg.default_level);
  }
  Configure(std::move(cfg));
  return true;
#else
  return false;
#endif
}

void Logger::ApplyEnvFileSink() {
  std::lock_guard lock(mu_);
  const char* f = std::getenv("GF_LOG_FILE");
  const char* d = std::getenv("GF_LOG_DIR");
  if (f != nullptr && f[0] != '\0') {
    cfg_.file_path = f;
  } else if (d != nullptr && d[0] != '\0') {
    cfg_.file_path = std::string(d) + "/giraffe_modules.log";
  } else {
    return;
  }
  bool has_file = false;
  for (const auto& s : cfg_.sinks) {
    if (s == "file") {
      has_file = true;
      break;
    }
  }
  if (!has_file) {
    cfg_.sinks.push_back("file");
  }
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

void Logger::WriteFile(std::string_view line) {
  if (cfg_.file_path.empty()) {
    return;
  }
  namespace fs = std::filesystem;
  std::error_code ec;
  if (cfg_.file_max_bytes > 0 && fs::exists(cfg_.file_path, ec)) {
    const auto sz = fs::file_size(cfg_.file_path, ec);
    if (!ec && sz >= cfg_.file_max_bytes) {
      const fs::path cur(cfg_.file_path);
      const fs::path bak = fs::path(cfg_.file_path + ".1");
      fs::remove(bak, ec);
      fs::rename(cur, bak, ec);
    }
  }
  std::ofstream out(cfg_.file_path, std::ios::app);
  if (out) {
    out << line << '\n';
  }
}

bool Logger::WantSink(std::string_view name) const {
  for (const auto& s : cfg_.sinks) {
    if (s == name) {
      return true;
    }
    if (name == "stdout" && (s == "console" || s == "stdout")) {
      return true;
    }
    if (name == "stderr" && (s == "console" || s == "stderr")) {
      return true;
    }
  }
  return false;
}

void Logger::EnsureDlt() {
  if (!WantSink("dlt")) {
    return;
  }
  DltSink::Instance().SetMaxContexts(cfg_.dlt_max_contexts);
  DltSink::Instance().Configure(cfg_.dlt_app_id, "Giraffe Flow");
}

void Logger::Log(std::string_view ctx, LogLevel level, std::string_view msg) {
  std::lock_guard lock(mu_);
  if (static_cast<std::uint8_t>(level) > static_cast<std::uint8_t>(EffectiveLevel(ctx))) {
    return;
  }
  EnsureDlt();
  const std::string plain =
      std::string("log: [") + ToString(level) + "] " + std::string(ctx) + " " + std::string(msg);
  const bool color = UseColor();
  const bool to_err = level <= LogLevel::kError;
  if (WantSink("file") || WantSink("serial")) {
    WriteFile(plain);
  }
  auto& out = to_err ? std::cerr : std::cout;
  const bool want_console =
      WantSink("console") || WantSink("stdout") || WantSink("stderr") || WantSink("serial") ||
      cfg_.sinks.empty();
  if (want_console) {
    if (color) {
      out << Ansi(level) << plain << "\033[0m" << std::endl;
    } else {
      out << plain << std::endl;
    }
  }
  if (WantSink("dlt")) {
    DltSink::Instance().Write(ctx, level, msg);
  }
}

}  // namespace gf_ara::log
