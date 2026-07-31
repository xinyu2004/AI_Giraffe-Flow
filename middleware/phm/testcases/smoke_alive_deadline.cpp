#include "gf_ara/exec/execution_client.hpp"
#include "gf_ara/phm/supervised_entity.hpp"
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
  using gf_ara::exec::ExecutionClient;
  using gf_ara::exec::ExecutionState;
  using gf_ara::phm::CheckpointStatus;
  using gf_ara::phm::SupervisedEntity;

  if (!ExecutionClient::Offer("phm.supervised.demo")) {
    return Fail("PHM-00", "Offer");
  }
  if (!ExecutionClient::ReportExecutionState(ExecutionState::kRunning)) {
    return Fail("PHM-00", "Running");
  }
  Pass("PHM-00", "exec Offer→Running");

  SupervisedEntity se{"demo_entity"};
  se.Configure(/*alive_cycle_ms=*/50, /*deadline_ms=*/80);

  if (se.Evaluate() != CheckpointStatus::kAliveMissed) {
    return Fail("PHM-01", "expected AliveMissed before first Alive");
  }
  Pass("PHM-01", "AliveMissed before first Alive");

  se.ReportAlive();
  if (se.Evaluate() != CheckpointStatus::kOk) {
    return Fail("PHM-02", "expected Ok after Alive");
  }
  gf::osal::SleepMs(20);
  if (!se.IsWithinDeadline()) {
    return Fail("PHM-02", "should still be within deadline");
  }
  Pass("PHM-02", "Alive→Ok within deadline");

  gf::osal::SleepMs(100);
  if (se.Evaluate() != CheckpointStatus::kDeadlineMissed) {
    return Fail("PHM-03", "expected DeadlineMissed");
  }
  se.ReportAlive();
  if (se.Evaluate() != CheckpointStatus::kOk) {
    return Fail("PHM-03", "expected recover after Alive");
  }
  Pass("PHM-03", "DeadlineMissed then recover");

  se.ReportLogical(false);
  if (se.Evaluate() != CheckpointStatus::kLogicalFault) {
    return Fail("PHM-04", "expected LogicalFault");
  }
  se.ReportLogical(true);
  if (se.Evaluate() != CheckpointStatus::kOk) {
    return Fail("PHM-04", "expected Ok after Logical recover");
  }
  Pass("PHM-04", "LogicalFault↔recover");

  se.SetPaused(true);
  gf::osal::SleepMs(120);
  if (se.Evaluate() != CheckpointStatus::kOk) {
    return Fail("PHM-05", "paused should suppress deadline");
  }
  Pass("PHM-05", "SetPaused suppresses deadline");

  std::cout << "gf_phm_alive_deadline_smoke OK exec=" << ExecutionClient::ProcessName()
            << " entity=" << se.Name() << "\n";
  return EXIT_SUCCESS;
}
