#ifndef GF_ARA_UCM_PACKAGE_MANAGER_HPP
#define GF_ARA_UCM_PACKAGE_MANAGER_HPP

#include <gf_ara/core/result.hpp>
#include <string>
#include <string_view>
#include <vector>

namespace gf_ara::ucm {

struct PackageInfo {
  std::string id;
  std::string version;
  std::string artifact_path;
  std::string target{"machine"};  // machine | cluster:<name>
};

enum class PackageState {
  kIdle,
  kTransferring,
  kPresent,      // transfer done, not yet processed
  kProcessing,
  kActivated,
  kRolledBack,
  kFailed
};

struct SoftwareCluster {
  std::string name;
  std::string version_file;
  std::vector<std::string> processes;
  std::string install_dir;
};

struct UcmRuntimeConfig {
  bool enabled{true};
  bool allow_rollback{true};
  bool allow_downgrade{false};
  std::string function_group{"MachineFG"};
  std::string package_source;
  std::string manifest_path;
  std::vector<SoftwareCluster> clusters;
};

/// Simplified package manager — gf_ara::ucm lite (not full ara::ucm).
class PackageManager {
 public:
  static gf_ara::core::Result<void> Initialize(std::string_view manifest_path);

  static gf_ara::core::Result<void> StartTransfer(const PackageInfo& info);
  /// Validate artifact (magic/manifest) → Present.
  static gf_ara::core::Result<void> ProcessSwPackage();
  static gf_ara::core::Result<void> Activate();
  static gf_ara::core::Result<void> Rollback();

  static PackageState GetState();
  static PackageInfo CurrentPackage();
  static std::string StoredVersion(std::string_view package_id);

  static void SetRuntimeConfig(UcmRuntimeConfig cfg);
  static const UcmRuntimeConfig& RuntimeConfig();

  /// Compare semver-ish dotted versions: -1 a<b, 0 equal, 1 a>b.
  static int CompareVersion(std::string_view a, std::string_view b);
};

}  // namespace gf_ara::ucm

#endif
