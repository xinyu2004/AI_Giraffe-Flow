#include "gf_ara/ucm/package_manager.hpp"

#include <mutex>
#include <string>

namespace gf_ara::ucm {
namespace {

std::mutex g_mu;
bool g_init{false};
PackageState g_state{PackageState::kIdle};
PackageInfo g_pkg;

}  // namespace

gf_ara::core::Result<void> PackageManager::Initialize(std::string_view manifest_path) {
  if (manifest_path.empty()) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kInvalidArgument);
  }
  std::lock_guard<std::mutex> lock(g_mu);
  g_init = true;
  g_state = PackageState::kIdle;
  g_pkg = {};
  return gf_ara::core::Result<void>::Ok();
}

gf_ara::core::Result<void> PackageManager::StartTransfer(const PackageInfo& info) {
  std::lock_guard<std::mutex> lock(g_mu);
  if (!g_init) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  if (g_state != PackageState::kIdle && g_state != PackageState::kRolledBack &&
      g_state != PackageState::kFailed) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kBusy);
  }
  if (info.id.empty() || info.artifact_path.empty()) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kInvalidArgument);
  }
  g_pkg = info;
  g_state = PackageState::kTransferring;
  return gf_ara::core::Result<void>::Ok();
}

gf_ara::core::Result<void> PackageManager::ProcessSwPackage() {
  std::lock_guard<std::mutex> lock(g_mu);
  if (g_state != PackageState::kTransferring) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  g_state = PackageState::kProcessing;
  return gf_ara::core::Result<void>::Ok();
}

gf_ara::core::Result<void> PackageManager::Activate() {
  std::lock_guard<std::mutex> lock(g_mu);
  if (g_state != PackageState::kProcessing) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  g_state = PackageState::kActivated;
  return gf_ara::core::Result<void>::Ok();
}

gf_ara::core::Result<void> PackageManager::Rollback() {
  std::lock_guard<std::mutex> lock(g_mu);
  if (g_state != PackageState::kActivated && g_state != PackageState::kProcessing &&
      g_state != PackageState::kFailed) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  g_state = PackageState::kRolledBack;
  return gf_ara::core::Result<void>::Ok();
}

PackageState PackageManager::GetState() {
  std::lock_guard<std::mutex> lock(g_mu);
  return g_state;
}

}  // namespace gf_ara::ucm
