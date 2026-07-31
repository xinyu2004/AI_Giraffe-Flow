#ifndef GF_ARA_LOG_LOGGER_HPP
#define GF_ARA_LOG_LOGGER_HPP

#include <cstdint>
#include <mutex>
#include <string>
#include <string_view>
#include <unordered_map>

namespace gf_ara::log {

enum class LogLevel : std::uint8_t {
  kFatal = 0,
  kError,
  kWarn,
  kInfo,
  kDebug,
  kVerbose,
};

struct LogConfig {
  LogLevel default_level{LogLevel::kInfo};
  std::unordered_map<std::string, LogLevel> contexts;
};

/// Minimal log lite (stdout/stderr). Not DLT.
class Logger {
 public:
  static Logger& Instance();

  void Configure(LogConfig cfg);
  /// Load `default_level` / `contexts[].id` + `level` from platform/log.yaml text.
  void ConfigureFromYaml(std::string_view yaml_text);
  [[nodiscard]] const LogConfig& Config() const noexcept { return cfg_; }

  void Log(std::string_view ctx, LogLevel level, std::string_view msg);
  void Fatal(std::string_view ctx, std::string_view msg) { Log(ctx, LogLevel::kFatal, msg); }
  void Error(std::string_view ctx, std::string_view msg) { Log(ctx, LogLevel::kError, msg); }
  void Warn(std::string_view ctx, std::string_view msg) { Log(ctx, LogLevel::kWarn, msg); }
  void Info(std::string_view ctx, std::string_view msg) { Log(ctx, LogLevel::kInfo, msg); }
  void Debug(std::string_view ctx, std::string_view msg) { Log(ctx, LogLevel::kDebug, msg); }

  [[nodiscard]] static const char* ToString(LogLevel level) noexcept;
  [[nodiscard]] static LogLevel ParseLevel(std::string_view s, LogLevel fallback) noexcept;

 private:
  Logger() = default;
  [[nodiscard]] LogLevel EffectiveLevel(std::string_view ctx) const;

  LogConfig cfg_{};
  mutable std::mutex mu_;
};

}  // namespace gf_ara::log

#endif
