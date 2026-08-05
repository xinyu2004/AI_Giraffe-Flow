#pragma once

#include <cstdint>
#include <functional>
#include <mutex>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

namespace gf_ara::collector {

enum class EventSeverity : std::uint8_t {
  kInfo = 0,
  kWarn,
  kError,
};

struct EventRecord {
  std::uint64_t t_ns{0};
  std::string source;  // phm | ucm | process | com
  std::string event_id;
  std::string detail;
  EventSeverity severity{EventSeverity::kError};
};

/// ISO 14229-1 status bit lite (subset).
struct DtcStatus {
  static constexpr std::uint8_t kTestFailed = 0x01;
  static constexpr std::uint8_t kPending = 0x04;
  static constexpr std::uint8_t kConfirmed = 0x08;
};

struct DtcEntry {
  std::uint32_t code{0};  // 3-byte DTC in low 24 bits
  std::uint8_t status{0};
  std::uint16_t occurrence{0};
  std::int16_t fdc{0};
  std::uint16_t aging_remaining{0};
  std::uint64_t freeze_t_ns{0};
  std::string freeze_blob;  // opaque snapshot (hex or text)
};

struct DtcMapEntry {
  std::uint32_t dtc{0};
  std::uint16_t debounce_count{1};
  std::uint32_t debounce_ms{0};
  std::int16_t fdc_inc{1};
  std::int16_t fdc_dec{1};
  std::int16_t fdc_threshold{3};
  std::uint16_t aging_cycles{40};
};

struct CollectorConfig {
  std::string forward{"local_store"};  // cp_dem | local_store | both
  bool local_enabled{true};
  std::uint32_t max_entries{256};
  std::unordered_map<std::string, DtcMapEntry> dtc_map;  // event_id → map
  std::vector<std::uint16_t> freeze_dids;                // optional DID list for freeze
};

/// Event Collector + DEM-lite (not Classic DEM).
/// DTC persist via gf_ara::per instance "dtc" when available (GF_PER_DIR).
class EventCollector {
 public:
  static EventCollector& Instance();

  void Configure(CollectorConfig cfg);
  [[nodiscard]] const CollectorConfig& Config() const noexcept { return cfg_; }

  /// Load dtc_map / debounce defaults from collector.yaml text (minimal scrape).
  void ConfigureFromYaml(std::string_view yaml_text);

  void ReportEvent(std::string_view source, std::string_view event_id,
                   std::string_view detail,
                   EventSeverity severity = EventSeverity::kError);

  /// Drive aging (call on operation cycle / SM→Running).
  void NotifyOperationCycle();

  void SetDtcControlEnabled(bool enabled);  // 0x85
  [[nodiscard]] bool DtcControlEnabled() const noexcept;

  /// Re-read DTC:* keys from GF_PER_DIR (cross-process SIL/DoIP share).
  void ReloadDtcsFromPer();

  [[nodiscard]] std::vector<DtcEntry> ListDtcs(std::uint8_t status_mask = 0xFF) const;
  [[nodiscard]] std::size_t CountDtcs(std::uint8_t status_mask = 0xFF) const;
  bool ClearDtc(std::uint32_t group_or_code);  // 0xFFFFFF = all
  [[nodiscard]] bool GetFreezeFrame(std::uint32_t dtc, std::string& blob_out,
                                    std::uint64_t& t_ns_out) const;

  void SetFreezeCapture(
      std::function<std::string(std::uint32_t dtc)> capture);

  [[nodiscard]] std::vector<EventRecord> Snapshot() const;
  [[nodiscard]] std::size_t Size() const;
  void Clear();

 private:
  EventCollector() = default;
  void EnsurePerLocked();
  void LoadDtcsFromPerLocked();
  void PersistDtcLocked(const DtcEntry& e);
  void DeleteDtcPerLocked(std::uint32_t code);
  void PersistCtrlLocked();
  void ApplyFaultLocked(std::string_view event_id, std::string_view detail);

  CollectorConfig cfg_{};
  bool dtc_control_on_{true};
  bool per_warned_{false};
  mutable std::mutex mu_;
  std::vector<EventRecord> ring_;
  std::unordered_map<std::uint32_t, DtcEntry> dtcs_;
  std::unordered_map<std::string, std::uint16_t> debounce_hits_;
  std::unordered_map<std::string, std::uint64_t> debounce_first_ns_;
  std::function<std::string(std::uint32_t)> freeze_capture_;
};

}  // namespace gf_ara::collector
