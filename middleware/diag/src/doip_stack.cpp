#include "gf_ara/diag/doip.hpp"

#include <mutex>
#include <vector>

namespace gf_ara::diag {
namespace {

std::mutex g_mu;
bool g_init{false};
DoipConfig g_cfg;
std::vector<std::uint8_t> g_rx;

}  // namespace

gf_ara::core::Result<void> DoipStack::Initialize(const DoipConfig& config) {
  if (config.logical_address.empty()) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kInvalidArgument);
  }
  std::lock_guard<std::mutex> lock(g_mu);
  g_cfg = config;
  g_init = true;
  g_rx.clear();
  return gf_ara::core::Result<void>::Ok();
}

gf_ara::core::Result<void> DoipStack::Shutdown() {
  std::lock_guard<std::mutex> lock(g_mu);
  if (!g_init) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  g_init = false;
  g_rx.clear();
  return gf_ara::core::Result<void>::Ok();
}

gf_ara::core::Result<RoutingActivationResponse> DoipStack::RequestRoutingActivation(
    std::uint16_t target_address) {
  std::lock_guard<std::mutex> lock(g_mu);
  if (!g_init) {
    return gf_ara::core::Result<RoutingActivationResponse>::Err(
        gf_ara::core::ErrorCode::kNotAvailable);
  }
  if (target_address == 0) {
    return gf_ara::core::Result<RoutingActivationResponse>::Ok(
        RoutingActivationResponse::kDenied);
  }
  return gf_ara::core::Result<RoutingActivationResponse>::Ok(
      RoutingActivationResponse::kSuccess);
}

gf_ara::core::Result<void> DoipStack::SendDiagnosticMessage(
    std::uint16_t target_address, std::vector<std::uint8_t> uds_payload) {
  std::lock_guard<std::mutex> lock(g_mu);
  if (!g_init) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  if (target_address == 0 || uds_payload.empty()) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kInvalidArgument);
  }
  // Echo stub: TesterPresent (0x3E) → positive 0x7E
  if (uds_payload[0] == 0x3E) {
    g_rx = {0x7E, 0x00};
  } else {
    g_rx = {0x7F, uds_payload[0], 0x11};  // NRC serviceNotSupported
  }
  return gf_ara::core::Result<void>::Ok();
}

gf_ara::core::Result<std::vector<std::uint8_t>> DoipStack::ReceiveDiagnosticMessage() {
  std::lock_guard<std::mutex> lock(g_mu);
  if (!g_init) {
    return gf_ara::core::Result<std::vector<std::uint8_t>>::Err(
        gf_ara::core::ErrorCode::kNotAvailable);
  }
  if (g_rx.empty()) {
    return gf_ara::core::Result<std::vector<std::uint8_t>>::Err(
        gf_ara::core::ErrorCode::kNotAvailable);
  }
  auto out = g_rx;
  g_rx.clear();
  return gf_ara::core::Result<std::vector<std::uint8_t>>::Ok(std::move(out));
}

}  // namespace gf_ara::diag
