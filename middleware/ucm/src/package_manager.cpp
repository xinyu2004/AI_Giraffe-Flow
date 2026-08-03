#include "gf_ara/ucm/package_manager.hpp"

#include <fstream>
#include <iostream>
#include <mutex>
#include <string>

namespace gf_ara::ucm {
namespace {

std::mutex g_mu;
bool g_init{false};
PackageState g_state{PackageState::kIdle};
PackageInfo g_pkg;

/** SIL flash backend: validate artifact looks like a real bundle (not empty junk). */
bool ArtifactLooksValid(const std::string& path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    std::cerr << "ucm: artifact missing: " << path << "\n";
    return false;
  }
  char mag[8]{};
  in.read(mag, 8);
  const auto n = in.gcount();
  if (n < 4) {
    std::cerr << "ucm: artifact too small: " << path << "\n";
    return false;
  }
  // GFSW = Giraffe Flow SIL SWU; PK = zip/swu; RAUC = rauc-like header
  const bool ok = (mag[0] == 'G' && mag[1] == 'F' && mag[2] == 'S' && mag[3] == 'W') ||
                  (mag[0] == 'P' && mag[1] == 'K') ||
                  (mag[0] == 'R' && mag[1] == 'A' && mag[2] == 'U' && mag[3] == 'C');
  if (!ok) {
    std::cerr << "ucm: artifact magic rejected (want GFSW/PK/RAUC): " << path << "\n";
  }
  return ok;
}

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
  std::string path;
  {
    std::lock_guard<std::mutex> lock(g_mu);
    if (g_state != PackageState::kTransferring) {
      return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
    }
    path = g_pkg.artifact_path;
  }
  if (!ArtifactLooksValid(path)) {
    std::lock_guard<std::mutex> lock(g_mu);
    g_state = PackageState::kFailed;
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kInvalidArgument);
  }
  // SIL flash stub (not real RAUC): stage “installed” marker next to artifact
  {
    std::ofstream mark(path + ".activated", std::ios::trunc);
    mark << "sil-activate ok path=" << path << "\n";
  }
  std::lock_guard<std::mutex> lock(g_mu);
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
      g_state != PackageState::kFailed && g_state != PackageState::kTransferring) {
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
