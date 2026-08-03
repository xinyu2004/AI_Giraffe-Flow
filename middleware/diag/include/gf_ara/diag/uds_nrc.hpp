#ifndef GF_ARA_DIAG_UDS_NRC_HPP
#define GF_ARA_DIAG_UDS_NRC_HPP

#include <cstdint>
#include <vector>

namespace gf_ara::diag {

/// Common ISO 14229 negative response codes (subset).
enum class UdsNrc : std::uint8_t {
  kGeneralReject = 0x10,
  kServiceNotSupported = 0x11,
  kSubFunctionNotSupported = 0x12,
  kIncorrectMessageLength = 0x13,
  kConditionsNotCorrect = 0x22,
  kRequestSequenceError = 0x24,
  kRequestOutOfRange = 0x31,
  kSecurityAccessDenied = 0x33,
  kInvalidKey = 0x35,
  kExceedNumberOfAttempts = 0x36,
  kRequiredTimeDelayNotExpired = 0x37,
  kUploadDownloadNotAccepted = 0x70,
  kTransferDataSuspended = 0x71,
  kGeneralProgrammingFailure = 0x72,
  kWrongBlockSequenceCounter = 0x73,
  kSubFunctionNotSupportedInActiveSession = 0x7E,
  kServiceNotSupportedInActiveSession = 0x7F,
};

[[nodiscard]] inline std::vector<std::uint8_t> MakeNrc(std::uint8_t sid, UdsNrc nrc) {
  return {0x7F, sid, static_cast<std::uint8_t>(nrc)};
}

}  // namespace gf_ara::diag

#endif
