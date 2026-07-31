#pragma once

#include <cstdint>
#include <mutex>
#include <string>
#include <string_view>
#include <vector>

namespace gf_ara::collector {

enum class EventSeverity : std::uint8_t {
  kInfo = 0,
  kWarn,
  kError,
};

struct EventRecord {
  std::uint64_t t_ns{0};
  std::string source;   // phm | process | com
  std::string event_id;
  std::string detail;
  EventSeverity severity{EventSeverity::kError};
};

struct CollectorConfig {
  std::string forward{"local_store"};  // cp_dem | local_store | both
  bool local_enabled{true};
  std::uint32_t max_entries{256};
};

/// In-process Event Collector (M3 min-set). Not Classic DEM.
class EventCollector {
 public:
  static EventCollector& Instance();

  void Configure(CollectorConfig cfg);
  [[nodiscard]] const CollectorConfig& Config() const noexcept { return cfg_; }

  void ReportEvent(std::string_view source, std::string_view event_id,
                   std::string_view detail,
                   EventSeverity severity = EventSeverity::kError);

  [[nodiscard]] std::vector<EventRecord> Snapshot() const;
  [[nodiscard]] std::size_t Size() const;
  void Clear();

 private:
  EventCollector() = default;
  CollectorConfig cfg_{};
  mutable std::mutex mu_;
  std::vector<EventRecord> ring_;
};

}  // namespace gf_ara::collector
