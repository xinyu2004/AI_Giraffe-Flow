// COLL-XPROC: two processes ReportEvent → shared NDJSON store (GF_COLLECTOR_STORE).
#include "gf_ara/collector/event_collector.hpp"

#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>
#include <sys/wait.h>
#include <unistd.h>

namespace {

int Fail(const char* id, const char* msg) {
  std::cerr << "CASE " << id << " FAIL " << msg << '\n';
  return 1;
}

void Pass(const char* id, const char* detail) {
  std::cout << "CASE " << id << " PASS " << detail << '\n';
}

void ChildReport(const char* tag) {
  using gf_ara::collector::CollectorConfig;
  using gf_ara::collector::EventCollector;
  using gf_ara::collector::EventSeverity;

  auto& col = EventCollector::Instance();
  CollectorConfig cfg;
  cfg.forward = "local_store";
  cfg.max_entries = 16;
  col.Configure(cfg);
  col.ReportEvent("phm", tag, std::string("entity=") + tag, EventSeverity::kError);
  _exit(0);
}

}  // namespace

int main() {
  const char* store_env = std::getenv("GF_COLLECTOR_STORE");
  std::string store =
      store_env && store_env[0] ? std::string(store_env) : "/tmp/gf_collector_xproc_$$.ndjson";
  if (!store_env || !store_env[0]) {
    store = "/tmp/gf_collector_xproc_" + std::to_string(static_cast<long>(::getpid())) + ".ndjson";
    ::setenv("GF_COLLECTOR_STORE", store.c_str(), 1);
  }
  ::unlink(store.c_str());

  const pid_t a = ::fork();
  if (a == 0) {
    ChildReport("AliveMissed");
  }
  const pid_t b = ::fork();
  if (b == 0) {
    ChildReport("LogicalFault");
  }
  int st = 0;
  ::waitpid(a, &st, 0);
  ::waitpid(b, &st, 0);

  std::ifstream in(store);
  if (!in) {
    return Fail("COLL-X01", "shared store missing");
  }
  std::string line;
  int lines = 0;
  bool saw_alive = false;
  bool saw_logical = false;
  while (std::getline(in, line)) {
    if (line.empty()) {
      continue;
    }
    ++lines;
    if (line.find("AliveMissed") != std::string::npos) {
      saw_alive = true;
    }
    if (line.find("LogicalFault") != std::string::npos) {
      saw_logical = true;
    }
  }
  if (lines < 2) {
    return Fail("COLL-X01", "expected ≥2 NDJSON lines from two processes");
  }
  Pass("COLL-X01", "shared store has ≥2 events");
  if (!saw_alive || !saw_logical) {
    return Fail("COLL-X02", "expected AliveMissed and LogicalFault ids");
  }
  Pass("COLL-X02", "events from both children visible in one store");

  std::cout << "gf_collector_xproc_smoke OK store=" << store << " lines=" << lines << "\n";
  ::unlink(store.c_str());
  return 0;
}
