#include "gf_ara/ucm/package_manager.hpp"

#include <gf_ara/per/key_value_storage.hpp>

#include <algorithm>
#include <fstream>
#include <iostream>
#include <mutex>
#include <sstream>
#include <string>
#include <vector>

namespace gf_ara::ucm {
namespace {

std::mutex g_mu;
bool g_init{false};
PackageState g_state{PackageState::kIdle};
PackageInfo g_pkg;
UcmRuntimeConfig g_rt;

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
  const bool ok = (mag[0] == 'G' && mag[1] == 'F' && mag[2] == 'S' && mag[3] == 'W') ||
                  (mag[0] == 'P' && mag[1] == 'K') ||
                  (mag[0] == 'R' && mag[1] == 'A' && mag[2] == 'U' && mag[3] == 'C');
  if (!ok) {
    std::cerr << "ucm: artifact magic rejected (want GFSW/PK/RAUC): " << path << "\n";
  }
  return ok;
}

std::vector<int> ParseParts(std::string_view v) {
  std::vector<int> parts;
  std::string cur;
  for (char c : v) {
    if (c == '.') {
      try {
        parts.push_back(std::stoi(cur));
      } catch (...) {
        parts.push_back(0);
      }
      cur.clear();
    } else if (c >= '0' && c <= '9') {
      cur.push_back(c);
    }
  }
  if (!cur.empty()) {
    try {
      parts.push_back(std::stoi(cur));
    } catch (...) {
      parts.push_back(0);
    }
  }
  return parts;
}

void PersistVersionLocked(const PackageInfo& info) {
  auto& kv = gf_ara::per::KeyValueStorage::Instance();
  if (!kv.IsOpen() || kv.InstanceName() != "ucm") {
    (void)kv.Open("ucm");
  }
  if (!kv.IsOpen()) {
    std::cerr << "ucm: WARN per unavailable; version not persisted\n";
    return;
  }
  (void)kv.SetValue(std::string("VER:") + info.id, info.version);
}

}  // namespace

int PackageManager::CompareVersion(std::string_view a, std::string_view b) {
  const auto pa = ParseParts(a);
  const auto pb = ParseParts(b);
  const auto n = std::max(pa.size(), pb.size());
  for (std::size_t i = 0; i < n; ++i) {
    const int x = i < pa.size() ? pa[i] : 0;
    const int y = i < pb.size() ? pb[i] : 0;
    if (x < y) {
      return -1;
    }
    if (x > y) {
      return 1;
    }
  }
  return 0;
}

void PackageManager::SetRuntimeConfig(UcmRuntimeConfig cfg) {
  std::lock_guard<std::mutex> lock(g_mu);
  g_rt = std::move(cfg);
}

const UcmRuntimeConfig& PackageManager::RuntimeConfig() {
  return g_rt;
}

std::string PackageManager::StoredVersion(std::string_view package_id) {
  auto& kv = gf_ara::per::KeyValueStorage::Instance();
  if (!kv.IsOpen() || kv.InstanceName() != "ucm") {
    (void)kv.Open("ucm");
  }
  if (!kv.IsOpen()) {
    return {};
  }
  const auto r = kv.GetValue(std::string("VER:") + std::string(package_id));
  return r.HasValue() ? r.Value() : std::string{};
}

gf_ara::core::Result<void> PackageManager::Initialize(std::string_view manifest_path) {
  if (manifest_path.empty()) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kInvalidArgument);
  }
  std::lock_guard<std::mutex> lock(g_mu);
  g_init = true;
  g_state = PackageState::kIdle;
  g_pkg = {};
  g_rt.manifest_path = std::string(manifest_path);
  return gf_ara::core::Result<void>::Ok();
}

gf_ara::core::Result<void> PackageManager::StartTransfer(const PackageInfo& info) {
  std::lock_guard<std::mutex> lock(g_mu);
  if (!g_init) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  if (g_state != PackageState::kIdle && g_state != PackageState::kRolledBack &&
      g_state != PackageState::kFailed && g_state != PackageState::kActivated) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kBusy);
  }
  if (info.id.empty() || info.artifact_path.empty()) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kInvalidArgument);
  }
  if (!g_rt.allow_downgrade && !info.version.empty()) {
    const auto cur = StoredVersion(info.id);
    if (!cur.empty() && CompareVersion(info.version, cur) < 0) {
      std::cerr << "ucm: downgrade rejected " << info.version << " < " << cur << "\n";
      g_state = PackageState::kFailed;
      return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kInvalidArgument);
    }
  }
  g_pkg = info;
  g_state = PackageState::kTransferring;
  return gf_ara::core::Result<void>::Ok();
}

gf_ara::core::Result<void> PackageManager::ProcessSwPackage() {
  std::string path;
  {
    std::lock_guard<std::mutex> lock(g_mu);
    if (g_state != PackageState::kTransferring && g_state != PackageState::kPresent) {
      return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
    }
    path = g_pkg.artifact_path;
  }
  if (!ArtifactLooksValid(path)) {
    std::lock_guard<std::mutex> lock(g_mu);
    g_state = PackageState::kFailed;
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kInvalidArgument);
  }
  {
    std::ofstream mark(path + ".activated", std::ios::trunc);
    mark << "sil-activate ok path=" << path << "\n";
  }
  std::lock_guard<std::mutex> lock(g_mu);
  g_state = PackageState::kPresent;
  // SIL: advance to Processing after Present (Verify step collapsed).
  g_state = PackageState::kProcessing;
  return gf_ara::core::Result<void>::Ok();
}

gf_ara::core::Result<void> PackageManager::Activate() {
  std::lock_guard<std::mutex> lock(g_mu);
  if (g_state != PackageState::kProcessing && g_state != PackageState::kPresent) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  g_state = PackageState::kProcessing;
  PersistVersionLocked(g_pkg);
  g_state = PackageState::kActivated;
  return gf_ara::core::Result<void>::Ok();
}

gf_ara::core::Result<void> PackageManager::Rollback() {
  std::lock_guard<std::mutex> lock(g_mu);
  if (g_state != PackageState::kActivated && g_state != PackageState::kProcessing &&
      g_state != PackageState::kFailed && g_state != PackageState::kTransferring &&
      g_state != PackageState::kPresent) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  g_state = PackageState::kRolledBack;
  return gf_ara::core::Result<void>::Ok();
}

PackageState PackageManager::GetState() {
  std::lock_guard<std::mutex> lock(g_mu);
  return g_state;
}

PackageInfo PackageManager::CurrentPackage() {
  std::lock_guard<std::mutex> lock(g_mu);
  return g_pkg;
}

}  // namespace gf_ara::ucm
