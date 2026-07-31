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

int Fail(const char* id, const char* msg) {
  std::cerr << "CASE " << id << " FAIL " << msg << '\n';
  return 1;
}

void Pass(const char* id, const char* detail) {
  std::cout << "CASE " << id << " PASS " << detail << '\n';
}

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
    return Fail("XIPC-01", "magic mismatch");
  }
  if (sizeof(FrameHeader) != 12) {
    return Fail("XIPC-01", "unexpected FrameHeader size");
  }
  Pass("XIPC-01", "FrameHeader layout");

  const pid_t pid = ::fork();
  if (pid < 0) {
    return Fail("XIPC-02", "fork failed");
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
    return Fail("XIPC-02", "connect failed");
  }
  Pass("XIPC-02", "Listen/Connect");

  if (!SendPod(client, MsgType::CanInfo20ms, d)) {
    return Fail("XIPC-03", "send failed");
  }
  Dummy back{};
  if (!RecvPod(client, MsgType::TrajPlot, &back) || back.a != 99) {
    return Fail("XIPC-03", "recv failed");
  }
  Pass("XIPC-03", "SendPod/RecvPod roundtrip");

  int status = 0;
  waitpid(pid, &status, 0);
  if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) {
    return Fail("XIPC-04", "child failed");
  }
  Pass("XIPC-04", "child exit 0");

  std::cout << "gf_cross_domain_ipc_smoke OK\n";
  return 0;
}
