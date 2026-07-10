#ifndef GF_OSAL_THREAD_HPP
#define GF_OSAL_THREAD_HPP

#include <cstdint>

namespace gf::osal {

/// Sleep for at least `ms` milliseconds (POSIX nanosleep).
void SleepMs(std::uint32_t ms) noexcept;

}  // namespace gf::osal

#endif
