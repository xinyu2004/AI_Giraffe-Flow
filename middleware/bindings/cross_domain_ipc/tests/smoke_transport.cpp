#include "gf_ara/com/binding/cross_domain_ipc/transport.hpp"

#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#include <cstdint>
#include <iostream>

namespace {

struct Dummy {
  uint32_t a{0};
  float b{0.f};
};

}  // namespace

int main() {
  using namespace gf_ara::com::binding::cross_domain_ipc;
  const char* path = "/tmp/gf_cp_ipc_smoke.sock";

  Dummy d{};
  d.a = 42;
  d.b = 1.5f;

  FrameHeader hdr{};
  hdr.type = static_cast<uint32_t>(MsgType::CanInfo20ms);
  hdr.size = static_cast<uint32_t>(sizeof(Dummy));
  if (hdr.magic != kMagic) {
    std::cerr << "smoke: magic mismatch\n";
    return 1;
  }
  if (sizeof(FrameHeader) != 12) {
    std::cerr << "smoke: unexpected FrameHeader size " << sizeof(FrameHeader) << "\n";
    return 1;
  }

  const pid_t pid = ::fork();
  if (pid < 0) {
    std::cerr << "smoke: fork failed\n";
    return 1;
  }
  if (pid == 0) {
    SocketTransport server;
    if (!server.ListenAndAccept(path)) {
      _exit(2);
    }
    Dummy recv{};
    if (!RecvPod(server, MsgType::CanInfo20ms, &recv) || recv.a != 42) {
      _exit(3);
    }
    Dummy reply{};
    reply.a = 99;
    reply.b = 3.f;
    if (!SendPod(server, MsgType::TrajPlot, reply)) {
      _exit(4);
    }
    _exit(0);
  }

  SocketTransport client;
  bool ok = false;
  for (int i = 0; i < 50; ++i) {
    if (client.Connect(path)) {
      ok = true;
      break;
    }
    usleep(20000);
  }
  if (!ok) {
    std::cerr << "smoke: connect failed\n";
    return 1;
  }
  if (!SendPod(client, MsgType::CanInfo20ms, d)) {
    std::cerr << "smoke: send failed\n";
    return 1;
  }
  Dummy back{};
  if (!RecvPod(client, MsgType::TrajPlot, &back) || back.a != 99) {
    std::cerr << "smoke: recv failed\n";
    return 1;
  }

  int status = 0;
  waitpid(pid, &status, 0);
  if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) {
    std::cerr << "smoke: child failed status=" << status << "\n";
    return 1;
  }
  std::cout << "gf_cross_domain_ipc_smoke OK\n";
  return 0;
}
