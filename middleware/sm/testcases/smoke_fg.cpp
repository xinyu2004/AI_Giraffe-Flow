#include "gf_ara/sm/state_client.hpp"

#include <iostream>

namespace {

int Fail(const char* id, const char* msg) {
  std::cerr << "CASE " << id << " FAIL " << msg << '\n';
  return 1;
}

void Pass(const char* id, const char* detail) {
  std::cout << "CASE " << id << " PASS " << detail << '\n';
}

}  // namespace

int main() {
  using gf_ara::sm::FunctionGroupState;
  using gf_ara::sm::StateClient;

  StateClient::EnsureGroup("MachineFG", FunctionGroupState::kRunning);
  if (StateClient::GetState("MachineFG") != FunctionGroupState::kRunning) {
    return Fail("SM-01", "initial Running");
  }
  Pass("SM-01", "EnsureGroup MachineFG Running");

  if (!StateClient::RequestTransition("MachineFG", FunctionGroupState::kUpdating)) {
    return Fail("SM-02", "Running→Updating");
  }
  if (StateClient::GetState("MachineFG") != FunctionGroupState::kUpdating) {
    return Fail("SM-02", "state Updating");
  }
  if (!StateClient::RequestTransition("MachineFG", FunctionGroupState::kRunning)) {
    return Fail("SM-02", "Updating→Running");
  }
  Pass("SM-02", "Running↔Updating");

  if (!StateClient::RequestTransition("MachineFG", FunctionGroupState::kOff)) {
    return Fail("SM-03", "Running→Off");
  }
  if (StateClient::RequestTransition("MachineFG", FunctionGroupState::kUpdating)) {
    return Fail("SM-03", "Off→Updating should be illegal");
  }
  Pass("SM-03", "Off; Off→Updating illegal");

  if (!StateClient::RequestTransition("MachineFG", FunctionGroupState::kRunning)) {
    return Fail("SM-04", "Off→Running");
  }
  Pass("SM-04", "Off→Running");

  StateClient::NotifyHealthFault("MachineFG", "demo_entity", "AliveMissed", false);
  if (StateClient::FaultCount("MachineFG") < 1) {
    return Fail("SM-05", "fault count");
  }
  Pass("SM-05", "NotifyHealthFault FaultCount");

  std::cout << "gf_sm_fg_smoke OK\n";
  return 0;
}
