#include "gf_ara/exec/execution_client.hpp"

#include <cstdlib>
#include <iostream>

int main() {
  using gf_ara::exec::ExecutionClient;
  using gf_ara::exec::ExecutionState;

  if (ExecutionClient::ReportExecutionState(ExecutionState::kRunning)) {
    std::cerr << "gf_exec_smoke FAIL: Report before Offer should fail\n";
    return EXIT_FAILURE;
  }
  if (!ExecutionClient::Offer("demo.app")) {
    std::cerr << "gf_exec_smoke FAIL: Offer\n";
    return EXIT_FAILURE;
  }
  if (ExecutionClient::GetState() != ExecutionState::kStarting) {
    std::cerr << "gf_exec_smoke FAIL: expected Starting\n";
    return EXIT_FAILURE;
  }
  if (!ExecutionClient::ReportExecutionState(ExecutionState::kRunning)) {
    std::cerr << "gf_exec_smoke FAIL: Report Running\n";
    return EXIT_FAILURE;
  }
  if (ExecutionClient::GetState() != ExecutionState::kRunning) {
    std::cerr << "gf_exec_smoke FAIL: expected Running\n";
    return EXIT_FAILURE;
  }
  std::cout << "gf_exec_smoke OK process=" << ExecutionClient::ProcessName() << "\n";
  return EXIT_SUCCESS;
}
