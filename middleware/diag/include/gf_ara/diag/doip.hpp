#ifndef GF_ARA_DIAG_DOIP_HPP
#define GF_ARA_DIAG_DOIP_HPP

#include <gf_ara/core/result.hpp>
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace gf_ara::diag {

struct DoipConfig {
  std::string logical_address;
  std::uint16_t source_address{0};
  std::uint16_t target_address{0};
  std::uint16_t udp_port{13400};
  std::uint16_t tcp_port{13400};
};

enum class RoutingActivationResponse : std::uint8_t {
  kUnknown = 0,
  kSuccess = 0x10,
  kDenied = 0x02
};

/// DoIP stack facade (placeholder — ISO 13400 subset).
class DoipStack {
 public:
  static gf_ara::core::Result<void> Initialize(const DoipConfig& config);
  static gf_ara::core::Result<void> Shutdown();

  static gf_ara::core::Result<RoutingActivationResponse> RequestRoutingActivation(
      std::uint16_t target_address);

  static gf_ara::core::Result<void> SendDiagnosticMessage(
      std::uint16_t target_address, std::vector<std::uint8_t> uds_payload);

  static gf_ara::core::Result<std::vector<std::uint8_t>> ReceiveDiagnosticMessage();
};

}  // namespace gf_ara::diag

#endif
