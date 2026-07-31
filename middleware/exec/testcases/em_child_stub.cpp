// Minimal child for OS EM smoke: stay alive until SIGTERM, or exit 75 if --exit-restart.
#include "gf_ara/exec/em_daemon.hpp"

#include <csignal>
#include <cstring>
#include <iostream>
#include <thread>
#include <chrono>

namespace {
volatile std::sig_atomic_t g_stop = 0;
void OnSig(int) { g_stop = 1; }
}  // namespace

int main(int argc, char** argv) {
  bool exit_restart = false;
  int hold_ms = 5000;
  for (int i = 1; i < argc; ++i) {
    if (std::strcmp(argv[i], "--exit-restart") == 0) {
      exit_restart = true;
    }
    if (std::strcmp(argv[i], "--hold-ms") == 0 && i + 1 < argc) {
      hold_ms = std::atoi(argv[++i]);
    }
  }
  std::signal(SIGTERM, OnSig);
  std::signal(SIGINT, OnSig);
  std::cout << "em_child_stub: start exit_restart=" << (exit_restart ? "1" : "0") << std::endl;
  if (exit_restart) {
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    std::cout << "em_child_stub: exit restart code=" << gf_ara::exec::kEmRestartExitCode
              << std::endl;
    return gf_ara::exec::kEmRestartExitCode;
  }
  const auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(hold_ms);
  while (!g_stop && std::chrono::steady_clock::now() < deadline) {
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
  }
  std::cout << "em_child_stub: exit 0\n";
  return 0;
}
