#include "gf/osal/clock.hpp"
#include "gf/osal/thread.hpp"

#include <cstdlib>
#include <iostream>

namespace {

int Fail(const char* id, const char* msg) {
  std::cerr << "CASE " << id << " FAIL " << msg << '\n';
  return EXIT_FAILURE;
}

void Pass(const char* id, const char* detail) {
  std::cout << "CASE " << id << " PASS " << detail << '\n';
}

}  // namespace

int main() {
  const auto t0 = gf::osal::MonotonicNowNs();
  gf::osal::SleepMs(20);
  const auto t1 = gf::osal::MonotonicNowNs();
  if (t1 <= t0) {
    return Fail("OSAL-01", "clock did not advance");
  }
  Pass("OSAL-01", "MonotonicNowNs advances");

  if ((t1 - t0) < 10ull * 1000000ull) {
    return Fail("OSAL-02", "sleep too short");
  }
  Pass("OSAL-02", "SleepMs ~20ms");

  std::cout << "gf_osal_smoke OK delta_ns=" << (t1 - t0) << "\n";
  return EXIT_SUCCESS;
}
