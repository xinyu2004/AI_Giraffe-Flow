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

  std::cout << "gf_collector_smoke OK entries=" << col.Size() << "\n";
  return 0;
}
