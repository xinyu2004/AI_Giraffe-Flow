#ifndef GF_ARA_LOG_LOGGER_HPP
#define GF_ARA_LOG_LOGGER_HPP

#include <cstdint>
#include <mutex>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

namespace gf_ara::log {

enum class LogLevel : std::uint8_t {
  kFatal = 0,
  kError,
  kWarn,
  kInfo,
  kDebug,
  kVerbose,
};

enum class ColorMode : std::uint8_t { kOff = 0, kOn, kAuto };

struct GmtExportConfig {
  bool enabled{false};
  LogLevel min_level{LogLevel::kError};
  std::vector<std::string> contexts;  // empty = any
  std::string mode{"pull"};
  std::uint32_t max_bytes{65536};
};

struct LogConfig {
  LogLevel default_level{LogLevel::kInfo};
  std::unordered_map<std::string, LogLevel> contexts;
  ColorMode color{ColorMode::kAuto};
  std::vector<std::string> sinks{"stdout", "stderr"};  // serial|file|stdout|stderr
  std::string file_path;
  std::uint32_t file_max_bytes{1024 * 1024};
  GmtExportConfig gmt_export{};
};

/// Minimal log lite. Not DLT.
class Logger {
 public:
  static Logger& Instance();

  void Configure(LogConfig cfg);
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

  /// Lines accepted by gmt_export whitelist (for host pull).
  [[nodiscard]] std::vector<std::string> DrainGmtExport();

 private:
  Logger() = default;
  [[nodiscard]] LogLevel EffectiveLevel(std::string_view ctx) const;
  [[nodiscard]] bool UseColor() const;
  [[nodiscard]] bool GmtAccepts(std::string_view ctx, LogLevel level) const;
  void WriteFile(std::string_view line);

  LogConfig cfg_{};
  mutable std::mutex mu_;
  std::vector<std::string> gmt_buf_;
  std::uint32_t gmt_bytes_{0};
};

}  // namespace gf_ara::log

#endif
