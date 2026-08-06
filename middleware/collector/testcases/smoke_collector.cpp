#include "gf_ara/collector/event_collector.hpp"

#include <iostream>

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
  using gf_ara::collector::EventCollector;
  using gf_ara::collector::EventSeverity;

  auto& col = EventCollector::Instance();
  col.Clear();

  CollectorConfig cfg;
  cfg.forward = "local_store";
  cfg.max_entries = 4;
  col.Configure(cfg);
  Pass("COLL-01", "Configure local_store max_entries=4");

  col.ReportEvent("phm", "AliveMissed", "entity=demo", EventSeverity::kError);
  col.ReportEvent("phm", "AliveMissed", "entity=demo2", EventSeverity::kError);
  col.ReportEvent("com", "Timeout", "svc=EgoMotion", EventSeverity::kWarn);
  col.ReportEvent("process", "Exit", "code=1", EventSeverity::kError);
  col.ReportEvent("phm", "LogicalFault", "entity=x", EventSeverity::kError);

  if (col.Size() != 4) {
    return Fail("COLL-02", "ring should keep max_entries");
  }
  Pass("COLL-02", "ring capped at max_entries");

  const auto snap = col.Snapshot();
  if (snap.size() != 4 || snap.back().event_id != "LogicalFault") {
    return Fail("COLL-03", "Snapshot contents");
  }
  Pass("COLL-03", "Snapshot last=LogicalFault");

  // FuSa latency sample: stamp span across ring (in-proc ReportEvent path)
  if (snap.front().t_ns > 0 && snap.back().t_ns >= snap.front().t_ns) {
    const auto span_us = (snap.back().t_ns - snap.front().t_ns) / 1000ULL;
    std::cout << "t_us_span=" << span_us << " collector ring first→last (n=" << snap.size()
              << ")\n";
  }

  // BL-COLL-FILTER: sources allowlist
  col.Clear();
  CollectorConfig filt;
  filt.forward = "local_store";
  filt.max_entries = 16;
  filt.sources = {"phm", "ucm"};
  col.Configure(filt);
  col.ReportEvent("phm", "AliveMissed", "ok", EventSeverity::kError);
  col.ReportEvent("com", "Timeout", "drop", EventSeverity::kWarn);
  col.ReportEvent("ucm", "ota_failed", "ok", EventSeverity::kError);
  col.ReportEvent("process", "Exit", "drop", EventSeverity::kError);
  if (col.Size() != 2) {
    return Fail("COLL-FILTER-01", "only phm+ucm should pass");
  }
  {
    const auto fs = col.Snapshot();
    if (fs.size() != 2 || fs[0].source != "phm" || fs[1].source != "ucm") {
      return Fail("COLL-FILTER-01", "unexpected snapshot after filter");
    }
  }
  Pass("COLL-FILTER-01", "sources allowlist drops com/process");

  col.Clear();
  col.ConfigureFromYaml(R"(
forward: local_store
sources:
  - phm
local:
  enabled: true
  max_entries: 8
)");
  col.ReportEvent("phm", "AliveMissed", "yaml", EventSeverity::kError);
  col.ReportEvent("ucm", "ota_failed", "no", EventSeverity::kError);
  if (col.Size() != 1 || col.Snapshot().front().source != "phm") {
    return Fail("COLL-FILTER-02", "ConfigureFromYaml sources");
  }
  Pass("COLL-FILTER-02", "ConfigureFromYaml sources allowlist");

  std::cout << "gf_collector_smoke OK entries=" << col.Size() << "\n";
  return 0;
}
