#ifndef GF_IOX_SMOKE_MSG_HPP
#define GF_IOX_SMOKE_MSG_HPP

#include <cstdint>

// Binding-local POD. Not a SKU / semantic type.
struct IoxSmokeMsg {
  std::uint64_t seq{};
  std::uint64_t stamp_ns{};
};

inline constexpr const char* kIoxSmokeService = "gf.iox.smoke";
inline constexpr const char* kIoxSmokeInstance = "1";
inline constexpr const char* kIoxSmokeEvent = "Msg";

#endif
