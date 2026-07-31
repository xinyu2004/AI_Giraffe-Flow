#include "gf_ara/exec/execution_client.hpp"

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

  if (ExecutionClient::ReportExecutionState(ExecutionState::kRunning)) {
    return Fail("EXEC-01", "Report before Offer should fail");
  }
  Pass("EXEC-01", "Report before Offer rejected");

  if (!ExecutionClient::Offer("demo.app")) {
    return Fail("EXEC-02", "Offer");
  }
  if (ExecutionClient::GetState() != ExecutionState::kStarting) {
    return Fail("EXEC-02", "expected Starting");
  }
  Pass("EXEC-02", "Offer → Starting");

  if (!ExecutionClient::ReportExecutionState(ExecutionState::kRunning)) {
    return Fail("EXEC-03", "Report Running");
  }
  if (ExecutionClient::GetState() != ExecutionState::kRunning) {
    return Fail("EXEC-03", "expected Running");
  }
  Pass("EXEC-03", "Report → Running");

  std::cout << "gf_exec_smoke OK process=" << ExecutionClient::ProcessName() << "\n";
  return EXIT_SUCCESS;
}
