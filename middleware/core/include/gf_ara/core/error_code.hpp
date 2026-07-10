#ifndef GF_ARA_CORE_ERROR_CODE_HPP
#define GF_ARA_CORE_ERROR_CODE_HPP

#include <cstdint>
#include <string_view>

namespace gf_ara::core {

enum class ErrorDomain : std::uint16_t {
  kCore = 1,
  kCom = 2,
};

enum class ErrorCode : std::uint32_t {
  kOk = 0,
  kUnknown = 1,
  kInvalidArgument = 2,
  kNotAvailable = 3,
  kBusy = 4,
  kTimeout = 5,
};

[[nodiscard]] inline constexpr std::string_view ToString(ErrorCode code) noexcept {
  switch (code) {
    case ErrorCode::kOk:
      return "Ok";
    case ErrorCode::kUnknown:
      return "Unknown";
    case ErrorCode::kInvalidArgument:
      return "InvalidArgument";
    case ErrorCode::kNotAvailable:
      return "NotAvailable";
    case ErrorCode::kBusy:
      return "Busy";
    case ErrorCode::kTimeout:
      return "Timeout";
  }
  return "Unknown";
}

}  // namespace gf_ara::core

#endif
