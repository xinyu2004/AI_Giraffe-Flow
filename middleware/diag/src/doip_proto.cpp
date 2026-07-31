#include "gf_ara/diag/doip_proto.hpp"

#include <cstring>

namespace gf_ara::diag {
namespace {

void PutBe16(std::vector<std::uint8_t>& out, std::uint16_t v) {
  out.push_back(static_cast<std::uint8_t>((v >> 8) & 0xff));
  out.push_back(static_cast<std::uint8_t>(v & 0xff));
}

void PutBe32(std::vector<std::uint8_t>& out, std::uint32_t v) {
  out.push_back(static_cast<std::uint8_t>((v >> 24) & 0xff));
  out.push_back(static_cast<std::uint8_t>((v >> 16) & 0xff));
  out.push_back(static_cast<std::uint8_t>((v >> 8) & 0xff));
  out.push_back(static_cast<std::uint8_t>(v & 0xff));
}

std::uint16_t GetBe16(const std::uint8_t* p) {
  return static_cast<std::uint16_t>((p[0] << 8) | p[1]);
}

std::uint32_t GetBe32(const std::uint8_t* p) {
  return (static_cast<std::uint32_t>(p[0]) << 24) |
         (static_cast<std::uint32_t>(p[1]) << 16) |
         (static_cast<std::uint32_t>(p[2]) << 8) |
         static_cast<std::uint32_t>(p[3]);
}

}  // namespace

std::vector<std::uint8_t> EncodeDoipFrame(const DoipFrame& frame) {
  std::vector<std::uint8_t> out;
  out.reserve(8 + frame.payload.size());
  out.push_back(frame.protocol_version);
  out.push_back(static_cast<std::uint8_t>(~frame.protocol_version));
  PutBe16(out, static_cast<std::uint16_t>(frame.payload_type));
  PutBe32(out, static_cast<std::uint32_t>(frame.payload.size()));
  out.insert(out.end(), frame.payload.begin(), frame.payload.end());
  return out;
}

std::optional<DoipFrame> TryDecodeDoipFrame(const std::vector<std::uint8_t>& buf,
                                            std::size_t& consumed) {
  consumed = 0;
  if (buf.size() < 8) {
    return std::nullopt;
  }
  const auto ver = buf[0];
  const auto inv = buf[1];
  if (static_cast<std::uint8_t>(~ver) != inv) {
    consumed = 1;  // resync: drop one byte
    return std::nullopt;
  }
  const auto ptype = GetBe16(buf.data() + 2);
  const auto plen = GetBe32(buf.data() + 4);
  if (plen > 65536) {
    consumed = 1;
    return std::nullopt;
  }
  if (buf.size() < 8 + plen) {
    return std::nullopt;
  }
  DoipFrame frame;
  frame.protocol_version = ver;
  frame.payload_type = static_cast<DoipPayloadType>(ptype);
  frame.payload.assign(buf.begin() + 8, buf.begin() + 8 + static_cast<std::ptrdiff_t>(plen));
  consumed = 8 + plen;
  return frame;
}

std::vector<std::uint8_t> MakeRoutingActivationRequest(std::uint16_t source_address,
                                                       std::uint8_t activation_type) {
  DoipFrame f;
  f.payload_type = DoipPayloadType::kRoutingActivationRequest;
  PutBe16(f.payload, source_address);
  f.payload.push_back(activation_type);
  f.payload.insert(f.payload.end(), {0, 0, 0, 0});  // reserved
  return EncodeDoipFrame(f);
}

std::vector<std::uint8_t> MakeRoutingActivationResponse(std::uint16_t tester_address,
                                                        std::uint16_t entity_address,
                                                        std::uint8_t response_code) {
  DoipFrame f;
  f.payload_type = DoipPayloadType::kRoutingActivationResponse;
  PutBe16(f.payload, tester_address);
  PutBe16(f.payload, entity_address);
  f.payload.push_back(response_code);
  f.payload.insert(f.payload.end(), {0, 0, 0, 0});  // reserved
  return EncodeDoipFrame(f);
}

std::vector<std::uint8_t> MakeDiagnosticMessage(std::uint16_t source_address,
                                                std::uint16_t target_address,
                                                const std::vector<std::uint8_t>& uds) {
  DoipFrame f;
  f.payload_type = DoipPayloadType::kDiagnosticMessage;
  PutBe16(f.payload, source_address);
  PutBe16(f.payload, target_address);
  f.payload.insert(f.payload.end(), uds.begin(), uds.end());
  return EncodeDoipFrame(f);
}

std::vector<std::uint8_t> MakeDiagnosticMessageAck(std::uint16_t source_address,
                                                   std::uint16_t target_address,
                                                   std::uint8_t ack_code) {
  DoipFrame f;
  f.payload_type = DoipPayloadType::kDiagnosticMessagePositiveAck;
  PutBe16(f.payload, source_address);
  PutBe16(f.payload, target_address);
  f.payload.push_back(ack_code);
  return EncodeDoipFrame(f);
}

}  // namespace gf_ara::diag
