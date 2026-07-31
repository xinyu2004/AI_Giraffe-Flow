#include "gf/osal/process.hpp"
#include "gf/osal/thread.hpp"

#include <cstdlib>
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
  using gf::osal::KillProcess;
  using gf::osal::ProcessSpawnRequest;
  using gf::osal::ProcessWaitStatus;
  using gf::osal::SpawnProcess;
  using gf::osal::TerminateProcess;
  using gf::osal::WaitProcess;
  using gf::osal::kInvalidProcessId;

  {
    ProcessSpawnRequest req;
    req.executable = "/bin/true";
    const auto id = SpawnProcess(req);
    if (!gf::osal::IsValidProcessId(id)) {
      return Fail("OSAL-P01", "SpawnProcess /bin/true");
    }
    Pass("OSAL-P01", "SpawnProcess");

    // Blocking wait for exit
    const auto wr = WaitProcess(id, false);
    if (wr.status != ProcessWaitStatus::kExited || wr.exit_code != 0) {
      return Fail("OSAL-P02", "WaitProcess exited 0");
    }
    Pass("OSAL-P02", "WaitProcess exited 0");
  }

  {
    ProcessSpawnRequest req;
    req.executable = "/bin/sleep";
    req.args = {"30"};
    const auto id = SpawnProcess(req);
    if (!gf::osal::IsValidProcessId(id)) {
      return Fail("OSAL-P03", "spawn sleep");
    }
    auto wr = WaitProcess(id, true);
    if (wr.status != ProcessWaitStatus::kStillRunning) {
      return Fail("OSAL-P03", "expected still running");
    }
    Pass("OSAL-P03", "nonblocking still running");

    if (!TerminateProcess(id)) {
      return Fail("OSAL-P04", "TerminateProcess");
    }
    // Reap
    for (int i = 0; i < 50; ++i) {
      wr = WaitProcess(id, true);
      if (wr.status != ProcessWaitStatus::kStillRunning) {
        break;
      }
      gf::osal::SleepMs(20);
    }
    if (wr.status == ProcessWaitStatus::kStillRunning) {
      (void)KillProcess(id);
      (void)WaitProcess(id, false);
      return Fail("OSAL-P04", "child did not stop");
    }
    Pass("OSAL-P04", "TerminateProcess + reap");
  }

  if (SpawnProcess(ProcessSpawnRequest{}) != kInvalidProcessId) {
    return Fail("OSAL-P05", "empty executable should fail");
  }
  Pass("OSAL-P05", "empty executable rejected");

  std::cout << "gf_osal_process_smoke OK\n";
  return EXIT_SUCCESS;
}
