#include "gf_ara/collector/event_collector.hpp"
#include "gf_ara/per/key_value_storage.hpp"

#include <cstdlib>
#include <filesystem>
#include <iostream>

namespace fs = std::filesystem;

namespace {

int Fail(const char* id, const char* msg) {
  std::cerr << "CASE " << id << " FAIL " << msg << '\n';
  return 1;
}

void Pass(const char* id, const char* detail) {
  std::cout << "CASE " << id << " PASS " << detail << '\n';
}

}  // namespace

int main() {
  using gf_ara::collector::CollectorConfig;
  using gf_ara::collector::DtcMapEntry;
  using gf_ara::collector::DtcStatus;
  using gf_ara::collector::EventCollector;
  using gf_ara::collector::EventSeverity;

  const auto dir = fs::temp_directory_path() / "gf_dem_smoke";
  fs::remove_all(dir);
  fs::create_directories(dir);
  ::setenv("GF_PER_DIR", dir.string().c_str(), 1);

  gf_ara::per::KeyValueStorage::Instance().ResetForTest();
  auto& col = EventCollector::Instance();
  col.Clear();
  (void)col.ClearDtc(0xFFFFFF);

  CollectorConfig cfg;
  cfg.forward = "local_store";
  DtcMapEntry map;
  map.dtc = 0x123456;
  map.debounce_count = 2;
  map.fdc_inc = 1;
  map.fdc_threshold = 2;
  map.aging_cycles = 2;
  cfg.dtc_map["phm/alive_timeout"] = map;
  col.Configure(cfg);

  // Below debounce — no confirmed
  col.ReportEvent("phm", "phm/alive_timeout", "e1", EventSeverity::kError);
  if (col.CountDtcs(DtcStatus::kConfirmed) != 0) {
    return Fail("DEM-01", "debounce should block");
  }
  Pass("DEM-01", "debounce blocks first hit");

  col.ReportEvent("phm", "phm/alive_timeout", "e2", EventSeverity::kError);
  col.ReportEvent("phm", "phm/alive_timeout", "e3", EventSeverity::kError);
  col.ReportEvent("phm", "phm/alive_timeout", "e4", EventSeverity::kError);
  if (col.CountDtcs(DtcStatus::kConfirmed) < 1) {
    return Fail("DEM-02", "should confirm after FDC");
  }
  Pass("DEM-02", "FDC confirms DTC");

  std::string blob;
  std::uint64_t t = 0;
  if (!col.GetFreezeFrame(0x123456, blob, t) || blob.empty()) {
    return Fail("DEM-03", "freeze frame missing");
  }
  Pass("DEM-03", "freeze frame captured");

  // Persist across reopen
  gf_ara::per::KeyValueStorage::Instance().Close();
  col.Configure(cfg);  // reloads from per
  if (col.CountDtcs(DtcStatus::kConfirmed) < 1) {
    return Fail("DEM-04", "persist across Configure/per reload");
  }
  Pass("DEM-04", "DTC persisted via gf_ara::per");

  col.SetDtcControlEnabled(false);
  const auto before = col.CountDtcs(0xFF);
  col.ReportEvent("phm", "phm/alive_timeout", "off", EventSeverity::kError);
  col.ReportEvent("phm", "phm/alive_timeout", "off2", EventSeverity::kError);
  col.ReportEvent("phm", "phm/alive_timeout", "off3", EventSeverity::kError);
  col.ReportEvent("phm", "phm/alive_timeout", "off4", EventSeverity::kError);
  if (col.CountDtcs(0xFF) != before) {
    return Fail("DEM-05", "0x85 off should freeze setting");
  }
  Pass("DEM-05", "DTC setting off freezes new confirms");
  col.SetDtcControlEnabled(true);

  // Aging: clear TF via cycles then remove
  col.NotifyOperationCycle();
  col.NotifyOperationCycle();
  col.NotifyOperationCycle();
  if (col.CountDtcs(DtcStatus::kConfirmed) != 0) {
    return Fail("DEM-06", "aging should clear");
  }
  Pass("DEM-06", "operation cycle aging clears DTC");

  col.ReportEvent("phm", "phm/alive_timeout", "a", EventSeverity::kError);
  col.ReportEvent("phm", "phm/alive_timeout", "b", EventSeverity::kError);
  col.ReportEvent("phm", "phm/alive_timeout", "c", EventSeverity::kError);
  col.ReportEvent("phm", "phm/alive_timeout", "d", EventSeverity::kError);
  if (!col.ClearDtc(0xFFFFFF)) {
    return Fail("DEM-07", "clear all");
  }
  if (col.CountDtcs(0xFF) != 0) {
    return Fail("DEM-07", "clear all leftover");
  }
  Pass("DEM-07", "0x14 clear all");

  fs::remove_all(dir);
  std::cout << "gf_dem_lite_smoke OK\n";
  return 0;
}
