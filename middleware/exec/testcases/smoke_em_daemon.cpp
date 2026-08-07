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
        << "    args: [\"--hold-ms\", \"400\"]\n"
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

  const int rc = em.RunForMs(2000);
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
  em.ShutdownAll();

  // --- EMD-05: dependency cycle must fail Load ---
  {
    std::ofstream(platform / "exec.yaml") << R"(
schema_version: "0.1"
function_groups:
  - id: MachineFG
    initial: Running
processes:
  - name: a
    function_group: MachineFG
    depends_on: [b]
    execution_client: true
  - name: b
    function_group: MachineFG
    depends_on: [a]
    execution_client: true
)";
    std::ofstream(tmp / "em_launch_cycle.yaml")
        << "schema_version: \"0.1\"\nprocesses:\n"
        << "  - name: a\n    binary: " << stub.string() << "\n    args: [\"--hold-ms\", \"50\"]\n"
        << "  - name: b\n    binary: " << stub.string() << "\n    args: [\"--hold-ms\", \"50\"]\n";
    gf_ara::exec::EmDaemon em_cycle;
    if (em_cycle.Load(platform.string(), (tmp / "em_launch_cycle.yaml").string(),
                      tmp.string(), logs.string())) {
      return Fail("EMD-05", "cycle should fail Load");
    }
    Pass("EMD-05", "dependency cycle rejected");
  }

  // --- EMD-06: unknown depends_on ---
  {
    std::ofstream(platform / "exec.yaml") << R"(
schema_version: "0.1"
function_groups:
  - id: MachineFG
    initial: Running
processes:
  - name: only
    function_group: MachineFG
    depends_on: [missing.dep]
    execution_client: true
)";
    std::ofstream(tmp / "em_launch_unk.yaml")
        << "schema_version: \"0.1\"\nprocesses:\n"
        << "  - name: only\n    binary: " << stub.string() << "\n    args: [\"--hold-ms\", \"50\"]\n";
    gf_ara::exec::EmDaemon em_unk;
    if (em_unk.Load(platform.string(), (tmp / "em_launch_unk.yaml").string(), tmp.string(),
                    logs.string())) {
      return Fail("EMD-06", "unknown depends_on should fail Load");
    }
    Pass("EMD-06", "unknown depends_on rejected");
  }

  // --- EMD-07: topo order base → mid → app (HOST-style platform then app) ---
  {
    std::ofstream(platform / "exec.yaml") << R"(
schema_version: "0.1"
function_groups:
  - id: MachineFG
    initial: Running
processes:
  - name: host.base
    function_group: MachineFG
    depends_on: []
    execution_client: false
  - name: host.mid
    function_group: MachineFG
    depends_on: [host.base]
    execution_client: false
  - name: app.top
    function_group: MachineFG
    depends_on: [host.mid]
    execution_client: true
)";
    std::ofstream(platform / "phm.yaml") << "schema_version: \"0.1\"\nentities: []\n";
    std::ofstream(tmp / "em_launch_ord.yaml")
        << "schema_version: \"0.1\"\nprocesses:\n"
        << "  - name: host.base\n    binary: " << stub.string()
        << "\n    args: [\"--hold-ms\", \"200\"]\n"
        << "  - name: host.mid\n    binary: " << stub.string()
        << "\n    args: [\"--hold-ms\", \"200\"]\n"
        << "  - name: app.top\n    binary: " << stub.string()
        << "\n    args: [\"--hold-ms\", \"200\"]\n";
    gf_ara::exec::EmDaemon em_ord;
    if (!em_ord.Load(platform.string(), (tmp / "em_launch_ord.yaml").string(), tmp.string(),
                     logs.string())) {
      return Fail("EMD-07", "Load order fixture");
    }
    const auto& procs = em_ord.Config().processes;
    if (procs.size() != 3 || procs[0].name != "host.base" || procs[1].name != "host.mid" ||
        procs[2].name != "app.top") {
      return Fail("EMD-07", "topo order not base→mid→app");
    }
    if (!em_ord.StartAll()) {
      return Fail("EMD-07", "StartAll");
    }
    Pass("EMD-07", "topo order base→mid→app + StartAll");
    em_ord.ShutdownAll();
  }

  // --- EMD-08: max_restarts cap (no infinite relaunch) ---
  {
    std::ofstream(platform / "exec.yaml") << R"(
schema_version: "0.1"
function_groups:
  - id: MachineFG
    initial: Running
processes:
  - name: stub.cap
    function_group: MachineFG
    depends_on: []
    execution_client: true
)";
    std::ofstream(platform / "phm.yaml") << R"(
schema_version: "0.1"
entities:
  - id: cap_alive
    process: stub.cap
    alive_period_ms: 50
    alive_timeout_ms: 200
    on_failure: restart
)";
    std::ofstream(tmp / "em_launch_cap.yaml")
        << "schema_version: \"0.1\"\nprocesses:\n"
        << "  - name: stub.cap\n    binary: " << stub.string() << "\n"
        << "    args: [\"--exit-restart\"]\n    max_restarts: 1\n";
    gf_ara::exec::EmDaemon em_cap;
    if (!em_cap.Load(platform.string(), (tmp / "em_launch_cap.yaml").string(), tmp.string(),
                     logs.string())) {
      return Fail("EMD-08", "Load");
    }
    if (!em_cap.StartAll()) {
      return Fail("EMD-08", "StartAll");
    }
    (void)em_cap.RunForMs(1500);
    if (em_cap.RestartCount("stub.cap") > 1) {
      return Fail("EMD-08", "restarts exceeded max_restarts=1");
    }
    Pass("EMD-08", "max_restarts capped");
    em_cap.ShutdownAll();
  }

  std::cout << "gf_em_daemon_smoke OK EMD-01..08\n";
  return EXIT_SUCCESS;
}
