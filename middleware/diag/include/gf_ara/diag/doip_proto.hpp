#ifndef GF_ARA_DIAG_DOIP_PROTO_HPP
#define GF_ARA_DIAG_DOIP_PROTO_HPP

#include <cstdint>
#include <optional>
#include <vector>

namespace gf_ara::diag {

/// ISO 13400-2 payload types (subset).
enum class DoipPayloadType : std::uint16_t {
  kRoutingActivationRequest = 0x0005,
  kRoutingActivationResponse = 0x0006,
  kDiagnosticMessage = 0x8001,
  kDiagnosticMessagePositiveAck = 0x8002,
  kDiagnosticMessageNegativeAck = 0x8003,
};

struct DoipFrame {
  std::uint8_t protocol_version{0x02};
  DoipPayloadType payload_type{DoipPayloadType::kDiagnosticMessage};
  std::vector<std::uint8_t> payload;
};

[[nodiscard]] std::vector<std::uint8_t> EncodeDoipFrame(const DoipFrame& frame);

/// Parse one complete frame from buffer; returns nullopt if need more bytes.
/// On success, consumes `consumed` bytes from the front of `buf`.
[[nodiscard]] std::optional<DoipFrame> TryDecodeDoipFrame(
    const std::vector<std::uint8_t>& buf, std::size_t& consumed);

[[nodiscard]] std::vector<std::uint8_t> MakeRoutingActivationRequest(
    std::uint16_t source_address, std::uint8_t activation_type = 0x00);

[[nodiscard]] std::vector<std::uint8_t> MakeRoutingActivationResponse(
    std::uint16_t tester_address, std::uint16_t entity_address,
    std::uint8_t response_code);

[[nodiscard]] std::vector<std::uint8_t> MakeDiagnosticMessage(
    std::uint16_t source_address, std::uint16_t target_address,
    const std::vector<std::uint8_t>& uds);

[[nodiscard]] std::vector<std::uint8_t> MakeDiagnosticMessageAck(
    std::uint16_t source_address, std::uint16_t target_address,
    std::uint8_t ack_code = 0x00);

}  // namespace gf_ara::diag

#endif
