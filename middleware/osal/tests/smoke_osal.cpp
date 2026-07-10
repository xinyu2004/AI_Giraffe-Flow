#include "gf/osal/clock.hpp"
#include "gf/osal/thread.hpp"

#include <cstdlib>
#include <iostream>

int main() {
  const auto t0 = gf::osal::MonotonicNowNs();
  gf::osal::SleepMs(20);
  const auto t1 = gf::osal::MonotonicNowNs();
  if (t1 <= t0) {
    std::cerr << "gf_osal_smoke FAIL: clock did not advance\n";
    return EXIT_FAILURE;
  }
  if ((t1 - t0) < 10ull * 1000000ull) {
    std::cerr << "gf_osal_smoke FAIL: sleep too short\n";
    return EXIT_FAILURE;
  }
  std::cout << "gf_osal_smoke OK delta_ns=" << (t1 - t0) << "\n";
  return EXIT_SUCCESS;
}
