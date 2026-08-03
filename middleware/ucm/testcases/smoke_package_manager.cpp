#include "gf_ara/ucm/package_manager.hpp"

#include <cstdlib>
#include <fstream>
#include <iostream>

namespace {

int Fail(const char* id, const char* msg) {
  std::cerr << "CASE " << id << " FAIL " << msg << '\n';
  return EXIT_FAILURE;
}

void Pass(const char* id, const char* detail) {
  std::cout << "CASE " << id << " PASS " << detail << '\n';
}

}  // namespace

int main() {
  using gf_ara::ucm::PackageInfo;
  using gf_ara::ucm::PackageManager;
  using gf_ara::ucm::PackageState;

  if (PackageManager::StartTransfer(PackageInfo{})) {
    return Fail("UCM-01", "StartTransfer before Init");
  }
  Pass("UCM-01", "StartTransfer before Init rejected");

  if (!PackageManager::Initialize("/tmp/gf_ucm_manifest.yaml")) {
    return Fail("UCM-02", "Initialize");
  }
  Pass("UCM-02", "Initialize");

  PackageInfo info;
  info.id = "pkg.demo";
  info.version = "1.0.0";
  info.artifact_path = "/tmp/gf_demo.swu";
  {
    std::ofstream f(info.artifact_path, std::ios::binary | std::ios::trunc);
    f.write("GFSW", 4);
    f.write("\x01\x00demo", 7);
  }

  if (!PackageManager::StartTransfer(info) ||
      PackageManager::GetState() != PackageState::kTransferring) {
    return Fail("UCM-03", "Transferring");
  }
  Pass("UCM-03", "StartTransfer → Transferring");

  if (!PackageManager::ProcessSwPackage() ||
      PackageManager::GetState() != PackageState::kProcessing) {
    return Fail("UCM-04", "Processing");
  }
  Pass("UCM-04", "ProcessSwPackage → Processing");

  if (!PackageManager::Activate() ||
      PackageManager::GetState() != PackageState::kActivated) {
    return Fail("UCM-05", "Activated");
  }
  Pass("UCM-05", "Activate");

  if (!PackageManager::Rollback() ||
      PackageManager::GetState() != PackageState::kRolledBack) {
    return Fail("UCM-06", "RolledBack");
  }
  Pass("UCM-06", "Rollback");

  std::cout << "gf_ucm_package_manager_smoke OK\n";
  return EXIT_SUCCESS;
}
