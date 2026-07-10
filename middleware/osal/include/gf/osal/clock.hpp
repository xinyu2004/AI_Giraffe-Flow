#ifndef GF_OSAL_CLOCK_HPP
#define GF_OSAL_CLOCK_HPP

#include <cstdint>

namespace gf::osal {

/// Monotonic time in nanoseconds (POSIX CLOCK_MONOTONIC).
[[nodiscard]] std::uint64_t MonotonicNowNs() noexcept;

}  // namespace gf::osal

#endif
