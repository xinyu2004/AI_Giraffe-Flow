#include "gf_ara/exec/em_daemon.hpp"
#include "gf_ara/sm/state_client.hpp"

#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <thread>

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
  fs::path self = fs::absolute(argv[0]).parent_path();
  fs::path stub = self / "gf_em_child_stub";
  if (!fs::exists(stub)) {
    stub = self / ".." / "gf_em_child_stub";
  }
  if (!fs::exists(stub)) {
    return Fail("FGD-01", "gf_em_child_stub not found");
  }

  const fs::path tmp = fs::temp_directory_path() / "gf_em_fg_setdiff_smoke";
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
    kind: machine
    initial: Running
  - id: DemoModeFG
    kind: mode
    initial: StateA
    states: [StateA, StateB]
processes:
  - name: stub.always
    function_group: MachineFG
    depends_on: []
    execution_client: true
  - name: stub.a
    function_group: DemoModeFG
    active_in: [StateA]
    depends_on: []
    execution_client: true
  - name: stub.b
    function_group: DemoModeFG
    active_in: [StateB]
    depends_on: []
    execution_client: true
)";
    std::ofstream(platform / "phm.yaml") << "schema_version: \"0.1\"\nentities: []\n";
    std::ofstream(tmp / "em_launch.yaml")
        << "schema_version: \"0.1\"\nprocesses:\n"
        << "  - name: stub.always\n"
        << "    binary: " << stub.string() << "\n"
        << "    args: [\"--hold-ms\", \"8000\"]\n"
        << "  - name: stub.a\n"
        << "    binary: " << stub.string() << "\n"
        << "    args: [\"--hold-ms\", \"8000\"]\n"
        << "  - name: stub.b\n"
        << "    binary: " << stub.string() << "\n"
        << "    args: [\"--hold-ms\", \"8000\"]\n";
  }

  gf_ara::exec::EmDaemon em;
  if (!em.Load(platform.string(), (tmp / "em_launch.yaml").string(), self.string(),
               logs.string())) {
    return Fail("FGD-02", "Load");
  }
  if (!em.StartAll()) {
    return Fail("FGD-02", "StartAll");
  }
  Pass("FGD-02", "StartAll seeded DemoModeFG=StateA");

  if (!em.IsRunning("stub.always") || !em.IsRunning("stub.a") || em.IsRunning("stub.b")) {
    return Fail("FGD-03", "membership StateA: always+a up, b held-off");
  }
  Pass("FGD-03", "StateA membership");

  if (!gf_ara::sm::StateClient::PublishFgState("DemoModeFG", "StateB")) {
    return Fail("FGD-04", "PublishFgState StateB");
  }
  for (int i = 0; i < 40; ++i) {
    if (!em.PollOnce()) {
      return Fail("FGD-04", "PollOnce");
    }
    if (em.IsRunning("stub.b") && !em.IsRunning("stub.a")) {
      break;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
  }
  if (!em.IsRunning("stub.always") || em.IsRunning("stub.a") || !em.IsRunning("stub.b")) {
    return Fail("FGD-04", "membership StateB after set-diff");
  }
  Pass("FGD-04", "StateA→StateB set-diff");

  em.ShutdownAll();
  std::cout << "gf_em_fg_setdiff_smoke OK\n";
  return EXIT_SUCCESS;
}
