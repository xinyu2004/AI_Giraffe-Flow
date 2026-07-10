#include "gf/osal/clock.hpp"

#include <ctime>

namespace gf::osal {

std::uint64_t MonotonicNowNs() noexcept {
  timespec ts{};
  if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) {
    return 0;
  }
  return static_cast<std::uint64_t>(ts.tv_sec) * 1000000000ull +
         static_cast<std::uint64_t>(ts.tv_nsec);
}

}  // namespace gf::osal
