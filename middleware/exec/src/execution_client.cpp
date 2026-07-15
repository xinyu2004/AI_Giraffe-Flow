#include "gf_ara/exec/execution_client.hpp"

#include <mutex>
#include <string>

namespace gf_ara::exec {
namespace {

std::mutex g_mu;
std::string g_name;
ExecutionState g_state{ExecutionState::kIdle};

}  // namespace

gf_ara::core::Result<void> ExecutionClient::Offer(std::string_view process_name) {
  if (process_name.empty()) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kInvalidArgument);
  }
  std::lock_guard<std::mutex> lock(g_mu);
  g_name.assign(process_name.begin(), process_name.end());
  g_state = ExecutionState::kStarting;
  return gf_ara::core::Result<void>::Ok();
}

gf_ara::core::Result<void> ExecutionClient::ReportExecutionState(ExecutionState state) {
  std::lock_guard<std::mutex> lock(g_mu);
  if (g_name.empty()) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  g_state = state;
  return gf_ara::core::Result<void>::Ok();
}

ExecutionState ExecutionClient::GetState() noexcept {
  std::lock_guard<std::mutex> lock(g_mu);
  return g_state;
}

std::string_view ExecutionClient::ProcessName() noexcept {
  std::lock_guard<std::mutex> lock(g_mu);
  return g_name;
}

}  // namespace gf_ara::exec
