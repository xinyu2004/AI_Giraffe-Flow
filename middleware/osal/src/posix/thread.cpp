#include "gf/osal/thread.hpp"

#include <ctime>

namespace gf::osal {

void SleepMs(std::uint32_t ms) noexcept {
  timespec ts{};
  ts.tv_sec = static_cast<time_t>(ms / 1000u);
  ts.tv_nsec = static_cast<long>((ms % 1000u) * 1000000u);
  while (nanosleep(&ts, &ts) != 0) {
    // retry on EINTR
  }
}

}  // namespace gf::osal
