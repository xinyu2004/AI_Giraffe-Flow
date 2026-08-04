#include "gf_ara/tsync/time_sync.hpp"

#include <chrono>
#include <iostream>
#include <thread>

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
  using gf_ara::tsync::SyncStatus;
  using gf_ara::tsync::TimeSyncProvider;
  using gf_ara::tsync::TsyncConfig;

  auto& ts = TimeSyncProvider::Instance();
  ts.Configure(TsyncConfig{});

  const auto t0 = ts.NowNs();
  std::this_thread::sleep_for(std::chrono::milliseconds(2));
  const auto t1 = ts.NowNs();
  if (t1 <= t0) {
    return Fail("TSYNC-01", "NowNs not monotonic");
  }
  Pass("TSYNC-01", "NowNs monotonic");

  if (ts.GetStatus() != SyncStatus::kSynchronized) {
    return Fail("TSYNC-02", "default status");
  }
  Pass("TSYNC-02", "Status=Synchronized (osal/mock)");

  TsyncConfig off;
  off.pretend_synchronized = false;
  ts.Configure(off);
  if (ts.GetStatus() != SyncStatus::kNotSynchronized) {
    return Fail("TSYNC-03", "pretend_synchronized=false");
  }
  Pass("TSYNC-03", "Status=NotSynchronized when configured");

  std::cout << "gf_tsync_smoke OK\n";
  return 0;
}
