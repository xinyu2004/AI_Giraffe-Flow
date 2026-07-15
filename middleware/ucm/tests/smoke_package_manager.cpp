#include "gf_ara/ucm/package_manager.hpp"

#include <cstdlib>
#include <iostream>

int main() {
  using gf_ara::ucm::PackageInfo;
  using gf_ara::ucm::PackageManager;
  using gf_ara::ucm::PackageState;

  if (PackageManager::StartTransfer(PackageInfo{})) {
    std::cerr << "gf_ucm_package_manager_smoke FAIL: StartTransfer before Init\n";
    return EXIT_FAILURE;
  }
  if (!PackageManager::Initialize("/tmp/gf_ucm_manifest.yaml")) {
    std::cerr << "gf_ucm_package_manager_smoke FAIL: Initialize\n";
    return EXIT_FAILURE;
  }

  PackageInfo info;
  info.id = "pkg.demo";
  info.version = "1.0.0";
  info.artifact_path = "/tmp/gf_demo.swu";

  if (!PackageManager::StartTransfer(info) ||
      PackageManager::GetState() != PackageState::kTransferring) {
    std::cerr << "gf_ucm_package_manager_smoke FAIL: Transferring\n";
    return EXIT_FAILURE;
  }
  if (!PackageManager::ProcessSwPackage() ||
      PackageManager::GetState() != PackageState::kProcessing) {
    std::cerr << "gf_ucm_package_manager_smoke FAIL: Processing\n";
    return EXIT_FAILURE;
  }
  if (!PackageManager::Activate() ||
      PackageManager::GetState() != PackageState::kActivated) {
    std::cerr << "gf_ucm_package_manager_smoke FAIL: Activated\n";
    return EXIT_FAILURE;
  }
  if (!PackageManager::Rollback() ||
      PackageManager::GetState() != PackageState::kRolledBack) {
    std::cerr << "gf_ucm_package_manager_smoke FAIL: RolledBack\n";
    return EXIT_FAILURE;
  }

  std::cout << "gf_ucm_package_manager_smoke OK\n";
  return EXIT_SUCCESS;
}
