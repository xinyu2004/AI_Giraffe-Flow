#include "gf_ara/exec/execution_client.hpp"
#include "gf_ara/exec/execution_manager.hpp"

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
  using gf_ara::exec::ExecutionManager;
  using gf_ara::exec::ExecutionState;

  ExecutionManager::ResetForTest();

  if (!ExecutionManager::StartProcess("app.demo")) {
    return Fail("EM-01", "StartProcess");
  }
  if (!ExecutionManager::IsRegistered("app.demo")) {
    return Fail("EM-01", "not registered");
  }
  Pass("EM-01", "StartProcess registers desired Running");

  if (!ExecutionClient::Offer("app.demo")) {
    return Fail("EM-02", "Offer");
  }
  if (ExecutionManager::ReportedState("app.demo") != ExecutionState::kStarting) {
    return Fail("EM-02", "EM reported Starting");
  }
  if (!ExecutionClient::ReportExecutionState(ExecutionState::kRunning)) {
    return Fail("EM-02", "Report Running");
  }
  if (ExecutionManager::ReportedState("app.demo") != ExecutionState::kRunning) {
    return Fail("EM-02", "EM reported Running");
  }
  Pass("EM-02", "Client Offer/Running mirrored in EM");

  if (!ExecutionManager::RequestRestart("app.demo", "AliveMissed")) {
    return Fail("EM-03", "RequestRestart");
  }
  if (ExecutionManager::RestartCount("app.demo") != 1) {
    return Fail("EM-03", "RestartCount");
  }
  if (!ExecutionManager::RestartPending("app.demo")) {
    return Fail("EM-03", "RestartPending");
  }
  if (ExecutionManager::ReportedState("app.demo") != ExecutionState::kStarting) {
    return Fail("EM-03", "after restart request state Starting");
  }
  Pass("EM-03", "RequestRestart count=1 pending");

  // Soft relaunch: Offer → Running again; consume pending
  if (!ExecutionClient::Offer("app.demo") ||
      !ExecutionClient::ReportExecutionState(ExecutionState::kRunning)) {
    return Fail("EM-04", "soft relaunch Offer/Running");
  }
  if (!ExecutionManager::ConsumeRestartPending("app.demo")) {
    return Fail("EM-04", "ConsumeRestartPending");
  }
  if (ExecutionManager::RestartPending("app.demo")) {
    return Fail("EM-04", "pending should be clear");
  }
  if (ExecutionManager::ReportedState("app.demo") != ExecutionState::kRunning) {
    return Fail("EM-04", "Running after soft relaunch");
  }
  Pass("EM-04", "soft relaunch + consume pending");

  std::cout << "gf_exec_em_smoke OK\n";
  return EXIT_SUCCESS;
}
