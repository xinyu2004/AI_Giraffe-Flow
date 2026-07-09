#ifndef GF_ARA_DIAG_UDS_TYPES_HPP
#define GF_ARA_DIAG_UDS_TYPES_HPP

#include <cstdint>

namespace gf_ara::diag {

enum class UdsServiceId : std::uint8_t {
  kDiagnosticSessionControl = 0x10,
  kEcuReset = 0x11,
  kReadDataByIdentifier = 0x22,
  kWriteDataByIdentifier = 0x2E,
  kRoutineControl = 0x31,
  kTesterPresent = 0x3E
};

struct UdsNegativeResponse {
  std::uint8_t sid{0x7F};
  std::uint8_t requested_service{0};
  std::uint8_t nrc{0};
};

}  // namespace gf_ara::diag

#endif
