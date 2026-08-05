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

struct LogConfig {
  LogLevel default_level{LogLevel::kInfo};
  std::unordered_map<std::string, LogLevel> contexts;
  ColorMode color{ColorMode::kAuto};
  /// console(=stdout+stderr) | stdout | stderr | file | serial | dlt
  std::vector<std::string> sinks{"stdout", "stderr"};
  std::string file_path;
  std::uint32_t file_max_bytes{1024 * 1024};  // rotate when exceeded (keeps path.1)
  std::string dlt_app_id{"GFAP"};
  std::uint32_t dlt_max_contexts{64};
};

/// Log lite with optional COVESA DLT sink (see docs/zh/operations/DLT_PLAN.md).
class Logger {
 public:
  static Logger& Instance();

  void Configure(LogConfig cfg);
  void ConfigureFromYaml(std::string_view yaml_text);
  /// After Configure*: honor GF_LOG_FILE or GF_LOG_DIR/giraffe_modules.log (file sink).
  void ApplyEnvFileSink();
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
  [[nodiscard]] bool UseColor() const;
  [[nodiscard]] bool WantSink(std::string_view name) const;
  void WriteFile(std::string_view line);
  void EnsureDlt();

  LogConfig cfg_{};
  mutable std::mutex mu_;
};

}  // namespace gf_ara::log

#endif
