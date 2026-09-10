#include "gf_ara/sm/state_client.hpp"

#include <iostream>
#include <string>

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

  // Generic ModeDeclaration FG (product names stay in Apps; smoke uses placeholders).
  constexpr const char* kModeFg = "DemoModeFG";
  constexpr const char* kStateA = "StateA";
  constexpr const char* kStateB = "StateB";
  StateClient::EnsureGroupNamed(kModeFg, kStateA);
  if (StateClient::GetStateNamed(kModeFg) != kStateA) {
    return Fail("SM-06", "Mode FG initial StateA");
  }
  if (!StateClient::RequestTransitionNamed(kModeFg, kStateB)) {
    return Fail("SM-06", "StateA→StateB");
  }
  if (StateClient::GetStateNamed(kModeFg) != kStateB) {
    return Fail("SM-06", "state StateB");
  }
  if (!StateClient::RequestTransitionNamed(kModeFg, kStateA)) {
    return Fail("SM-06", "StateB→StateA");
  }
  Pass("SM-06", "ModeDeclaration named transitions");

  if (!StateClient::PublishFgState("ChassisFG", "EmbActive")) {
    return Fail("SM-07", "PublishFgState ChassisFG");
  }
  if (StateClient::ReadFgState("ChassisFG") != "EmbActive") {
    return Fail("SM-07", "ReadFgState ChassisFG");
  }
  if (!StateClient::PublishFgState(kModeFg, kStateB)) {
    return Fail("SM-07", "PublishFgState DemoModeFG");
  }
  if (StateClient::ReadFgState(kModeFg) != kStateB) {
    return Fail("SM-07", "ReadFgState DemoModeFG");
  }
  if (StateClient::ReadFgState("ChassisFG") != "EmbActive") {
    return Fail("SM-07", "ChassisFG state clobbered");
  }
  Pass("SM-07", "FgStateStore multi-FG Publish/Read");

  std::cout << "gf_sm_fg_smoke OK\n";
  return 0;
}
