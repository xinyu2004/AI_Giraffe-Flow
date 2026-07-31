#include "gf_ara/exec/execution_manager.hpp"

#include <iostream>
#include <mutex>
#include <string>
#include <unordered_map>

namespace gf_ara::exec {
namespace {

struct Entry {
  ExecutionState reported{ExecutionState::kIdle};
  ExecutionState desired{ExecutionState::kIdle};
  std::uint32_t restarts{0};
  bool restart_pending{false};
};

std::mutex& Mu() {
  static std::mutex m;
  return m;
}

std::unordered_map<std::string, Entry>& Table() {
  static std::unordered_map<std::string, Entry> t;
  return t;
}

Entry* Find(std::string_view name) {
  auto& t = Table();
  auto it = t.find(std::string(name));
  if (it == t.end()) {
    return nullptr;
  }
  return &it->second;
}

Entry& Ensure(std::string_view name) {
  return Table()[std::string(name)];
}

}  // namespace

void ExecutionManager::ResetForTest() {
  std::lock_guard lock(Mu());
  Table().clear();
}

void ExecutionManager::RegisterProcess(std::string_view name) {
  if (name.empty()) {
    return;
  }
  std::lock_guard lock(Mu());
  Ensure(name);
}

bool ExecutionManager::StartProcess(std::string_view name) {
  if (name.empty()) {
    return false;
  }
  std::lock_guard lock(Mu());
  auto& e = Ensure(name);
  e.desired = ExecutionState::kRunning;
  if (e.reported == ExecutionState::kIdle || e.reported == ExecutionState::kTerminating) {
    // Launch requested; client Offer will move to Starting.
    std::cout << "em: start_process name=" << name << " (desired=Running)\n";
  }
  return true;
}

void ExecutionManager::OnClientOffer(std::string_view name) {
  if (name.empty()) {
    return;
  }
  std::lock_guard lock(Mu());
  auto& e = Ensure(name);
  e.reported = ExecutionState::kStarting;
  if (e.desired == ExecutionState::kIdle) {
    e.desired = ExecutionState::kRunning;
  }
}

void ExecutionManager::OnClientState(std::string_view name, ExecutionState state) {
  if (name.empty()) {
    return;
  }
  std::lock_guard lock(Mu());
  auto& e = Ensure(name);
  e.reported = state;
}

bool ExecutionManager::RequestRestart(std::string_view name, std::string_view reason) {
  if (name.empty()) {
    return false;
  }
  std::lock_guard lock(Mu());
  auto& e = Ensure(name);
  ++e.restarts;
  e.restart_pending = true;
  e.desired = ExecutionState::kRunning;
  e.reported = ExecutionState::kStarting;
  std::cout << "em: restart_request name=" << name << " reason=" << reason
            << " count=" << e.restarts << std::endl;
  return true;
}

std::uint32_t ExecutionManager::RestartCount(std::string_view name) noexcept {
  std::lock_guard lock(Mu());
  const Entry* e = Find(name);
  return e ? e->restarts : 0;
}

bool ExecutionManager::RestartPending(std::string_view name) noexcept {
  std::lock_guard lock(Mu());
  const Entry* e = Find(name);
  return e && e->restart_pending;
}

bool ExecutionManager::ConsumeRestartPending(std::string_view name) {
  std::lock_guard lock(Mu());
  Entry* e = Find(name);
  if (!e || !e->restart_pending) {
    return false;
  }
  e->restart_pending = false;
  return true;
}

ExecutionState ExecutionManager::ReportedState(std::string_view name) noexcept {
  std::lock_guard lock(Mu());
  const Entry* e = Find(name);
  return e ? e->reported : ExecutionState::kIdle;
}

bool ExecutionManager::IsRegistered(std::string_view name) noexcept {
  std::lock_guard lock(Mu());
  return Find(name) != nullptr;
}

}  // namespace gf_ara::exec
