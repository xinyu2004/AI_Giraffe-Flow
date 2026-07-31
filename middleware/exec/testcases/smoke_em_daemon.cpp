#include "gf_ara/exec/em_daemon.hpp"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>

namespace fs = std::filesystem;

namespace {

int Fail(const char* id, const char* msg) {
  std::cerr << "CASE " << id << " FAIL " << msg << '\n';
  return EXIT_FAILURE;
}

void Pass(const char* id, const char* detail) {
  std::cout << "CASE " << id << " PASS " << detail << '\n';
}

}  // namespace

int main(int argc, char** argv) {
  // Locate gf_em_child_stub next to this binary or via argv[0] dir
  fs::path self = fs::absolute(argv[0]).parent_path();
  fs::path stub = self / "gf_em_child_stub";
  if (!fs::exists(stub)) {
    stub = self / ".." / "gf_em_child_stub";
  }
  if (!fs::exists(stub)) {
    // cmake places both under middleware/exec/
    stub = self / "gf_em_child_stub";
  }
  if (!fs::exists(stub)) {
    return Fail("EMD-01", "gf_em_child_stub not found");
  }

  const fs::path tmp = fs::temp_directory_path() / "gf_em_daemon_smoke";
  fs::create_directories(tmp);
  const fs::path platform = tmp / "platform";
  fs::create_directories(platform);
  const fs::path logs = tmp / "logs";
  fs::create_directories(logs);

  {
    std::ofstream(platform / "exec.yaml") << R"(
schema_version: "0.1"
function_groups:
  - id: MachineFG
    initial: Running
processes:
  - name: stub.keeper
    function_group: MachineFG
    depends_on: []
    execution_client: true
  - name: stub.restarter
    function_group: MachineFG
    depends_on:
      - stub.keeper
    execution_client: true
)";
    std::ofstream(platform / "phm.yaml") << R"(
schema_version: "0.1"
entities:
  - id: restarter_alive
    process: stub.restarter
    alive_period_ms: 100
    alive_timeout_ms: 300
    on_failure: restart
)";
    std::ofstream(tmp / "em_launch.yaml")
        << "schema_version: \"0.1\"\nprocesses:\n"
        << "  - name: stub.keeper\n"
        << "    binary: " << stub.string() << "\n"
        << "    args: [\"--hold-ms\", \"2000\"]\n"
        << "  - name: stub.restarter\n"
        << "    binary: " << stub.string() << "\n"
        << "    args: [\"--exit-restart\"]\n"
        << "    max_restarts: 2\n";
  }
  Pass("EMD-01", "wrote fixture platform + launch");

  gf_ara::exec::EmDaemon em;
  if (!em.Load(platform.string(), (tmp / "em_launch.yaml").string(), tmp.string(),
               logs.string())) {
    return Fail("EMD-02", "Load");
  }
  // build_dir unused for absolute binaries; stub path absolute in launch
  if (em.Config().processes.size() != 2) {
    return Fail("EMD-02", "expected 2 processes");
  }
  if (em.Config().processes[0].name != "stub.keeper") {
    return Fail("EMD-02", "topo: keeper should be first");
  }
  if (!em.Config().processes[1].restart_enabled) {
    return Fail("EMD-02", "restarter should have restart_enabled from phm");
  }
  Pass("EMD-02", "Load topo + restart_enabled");

  if (!em.StartAll()) {
    return Fail("EMD-03", "StartAll");
  }
  Pass("EMD-03", "StartAll spawned");

  const int rc = em.RunForMs(8000);
  if (rc != 0) {
    return Fail("EMD-04", "RunForMs non-zero");
  }
  if (em.LaunchCount("stub.restarter") < 2) {
    std::cerr << "launches=" << em.LaunchCount("stub.restarter") << "\n";
    return Fail("EMD-04", "expected restarter relaunch launches>=2");
  }
  if (em.RestartCount("stub.restarter") < 1) {
    return Fail("EMD-04", "expected RestartCount>=1");
  }
  Pass("EMD-04", "OS relaunch on exit 75");

  std::cout << "gf_em_daemon_smoke OK launches_restarter="
            << em.LaunchCount("stub.restarter")
            << " restarts=" << em.RestartCount("stub.restarter") << "\n";
  return EXIT_SUCCESS;
}
