#include "gf_ara/exec/execution_client.hpp"
#include "gf_ara/phm/supervised_entity.hpp"
#include "gf/osal/thread.hpp"

#include <cstdlib>
#include <iostream>

int main() {
  using gf_ara::exec::ExecutionClient;
  using gf_ara::exec::ExecutionState;
  using gf_ara::phm::CheckpointStatus;
  using gf_ara::phm::SupervisedEntity;

  // E 轨闭环：exec 报 Running → phm Alive/Deadline
  if (!ExecutionClient::Offer("phm.supervised.demo")) {
    std::cerr << "gf_phm_alive_deadline_smoke FAIL: Offer\n";
    return EXIT_FAILURE;
  }
  if (!ExecutionClient::ReportExecutionState(ExecutionState::kRunning)) {
    std::cerr << "gf_phm_alive_deadline_smoke FAIL: Running\n";
    return EXIT_FAILURE;
  }

  SupervisedEntity se{"demo_entity"};
  se.Configure(/*alive_cycle_ms=*/50, /*deadline_ms=*/80);

  if (se.Evaluate() != CheckpointStatus::kAliveMissed) {
    std::cerr << "gf_phm_alive_deadline_smoke FAIL: expected AliveMissed before first Alive\n";
    return EXIT_FAILURE;
  }

  se.ReportAlive();
  if (se.Evaluate() != CheckpointStatus::kOk) {
    std::cerr << "gf_phm_alive_deadline_smoke FAIL: expected Ok after Alive\n";
    return EXIT_FAILURE;
  }

  gf::osal::SleepMs(20);
  if (!se.IsWithinDeadline()) {
    std::cerr << "gf_phm_alive_deadline_smoke FAIL: should still be within deadline\n";
    return EXIT_FAILURE;
  }

  gf::osal::SleepMs(100);
  if (se.Evaluate() != CheckpointStatus::kDeadlineMissed) {
    std::cerr << "gf_phm_alive_deadline_smoke FAIL: expected DeadlineMissed\n";
    return EXIT_FAILURE;
  }

  se.ReportAlive();
  if (se.Evaluate() != CheckpointStatus::kOk) {
    std::cerr << "gf_phm_alive_deadline_smoke FAIL: expected recover after Alive\n";
    return EXIT_FAILURE;
  }

  // UCM/SM hook: pause during update
  se.SetPaused(true);
  gf::osal::SleepMs(120);
  if (se.Evaluate() != CheckpointStatus::kOk) {
    std::cerr << "gf_phm_alive_deadline_smoke FAIL: paused should suppress deadline\n";
    return EXIT_FAILURE;
  }

  std::cout << "gf_phm_alive_deadline_smoke OK exec=" << ExecutionClient::ProcessName()
            << " entity=" << se.Name() << "\n";
  return EXIT_SUCCESS;
}
