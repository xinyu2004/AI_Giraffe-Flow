#include "gf_ara/sm/state_client.hpp"

#include <iostream>
#include <mutex>

namespace gf_ara::sm {
namespace {

std::mutex& Mutex() {
  static std::mutex m;
  return m;
}

bool Allowed(FunctionGroupState from, FunctionGroupState to) noexcept {
  if (from == to) {
    return true;
  }
  // Off → Running → Updating → Running; Updating/Running → Off
  switch (from) {
    case FunctionGroupState::kOff:
      return to == FunctionGroupState::kRunning;
    case FunctionGroupState::kRunning:
      return to == FunctionGroupState::kUpdating || to == FunctionGroupState::kOff;
    case FunctionGroupState::kUpdating:
      return to == FunctionGroupState::kRunning || to == FunctionGroupState::kOff;
  }
  return false;
}

}  // namespace

const char* ToString(FunctionGroupState s) noexcept {
  switch (s) {
    case FunctionGroupState::kOff:
      return "Off";
    case FunctionGroupState::kRunning:
      return "Running";
    case FunctionGroupState::kUpdating:
      return "Updating";
  }
  return "?";
}

std::unordered_map<std::string, StateClient::Entry>& StateClient::Table() {
  static std::unordered_map<std::string, Entry> t;
  return t;
}

void StateClient::EnsureGroup(std::string_view fg_id, FunctionGroupState initial) {
  if (fg_id.empty()) {
    return;
  }
  std::lock_guard lock(Mutex());
  auto& table = Table();
  const auto key = std::string(fg_id);
  const auto [it, inserted] = table.try_emplace(key);
  if (inserted) {
    it->second.state = initial;
    std::cout << "sm: ensure fg=" << fg_id << " initial=" << ToString(initial)
              << std::endl;
  }
}

FunctionGroupState StateClient::GetState(std::string_view fg_id) noexcept {
  std::lock_guard lock(Mutex());
  const auto it = Table().find(std::string(fg_id));
  if (it == Table().end()) {
    return FunctionGroupState::kOff;
  }
  return it->second.state;
}

bool StateClient::RequestTransition(std::string_view fg_id, FunctionGroupState target) {
  if (fg_id.empty()) {
    return false;
  }
  std::lock_guard lock(Mutex());
  auto& e = Table()[std::string(fg_id)];
  if (!Allowed(e.state, target)) {
    std::cerr << "sm: illegal transition fg=" << fg_id << " " << ToString(e.state)
              << "→" << ToString(target) << "\n";
    return false;
  }
  if (e.state != target) {
    std::cout << "sm: transition fg=" << fg_id << " " << ToString(e.state) << "→"
              << ToString(target) << std::endl;
    e.state = target;
  }
  return true;
}

void StateClient::NotifyHealthFault(std::string_view fg_id, std::string_view entity,
                                    std::string_view reason, bool enter_updating) {
  if (fg_id.empty()) {
    fg_id = "MachineFG";
  }
  {
    std::lock_guard lock(Mutex());
    auto& e = Table()[std::string(fg_id)];
    ++e.faults;
    std::cout << "sm: health_fault fg=" << fg_id << " entity=" << entity
              << " reason=" << reason << " faults=" << e.faults << std::endl;
  }
  if (enter_updating) {
    RequestTransition(fg_id, FunctionGroupState::kUpdating);
  }
}

std::uint32_t StateClient::FaultCount(std::string_view fg_id) noexcept {
  std::lock_guard lock(Mutex());
  const auto it = Table().find(std::string(fg_id));
  if (it == Table().end()) {
    return 0;
  }
  return it->second.faults;
}

}  // namespace gf_ara::sm
