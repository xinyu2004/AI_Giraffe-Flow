#ifndef GF_ARA_UCM_PACKAGE_MANAGER_HPP
#define GF_ARA_UCM_PACKAGE_MANAGER_HPP

#include <gf_ara/core/result.hpp>
#include <string>
#include <string_view>

namespace gf_ara::ucm {

/// OTA package descriptor (placeholder — fields frozen in Phase 0).
struct PackageInfo {
  std::string id;
  std::string version;
  std::string artifact_path;
};

enum class PackageState {
  kIdle,
  kTransferring,
  kProcessing,
  kActivated,
  kRolledBack,
  kFailed
};

/// Simplified package manager — maps to ara::ucm subset.
class PackageManager {
 public:
  static gf_ara::core::Result<void> Initialize(std::string_view manifest_path);

  static gf_ara::core::Result<void> StartTransfer(const PackageInfo& info);
  static gf_ara::core::Result<void> ProcessSwPackage();
  static gf_ara::core::Result<void> Activate();
  static gf_ara::core::Result<void> Rollback();

  static PackageState GetState();
};

}  // namespace gf_ara::ucm

#endif
