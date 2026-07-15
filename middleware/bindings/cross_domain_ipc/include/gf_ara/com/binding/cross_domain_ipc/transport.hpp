#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

namespace gf_ara::com::binding::cross_domain_ipc {

constexpr uint32_t kMagic = 0x47465849u;  // 'GFXI'
constexpr const char* kDefaultSockPath = "/tmp/gf_cp_ipc.sock";

enum class MsgType : uint32_t {
  CanInfo20ms = 1,
  CanInfo10ms = 2,
  CanInfo100ms = 3,
  TrajPlot = 4,
  PParking = 5,
};

struct FrameHeader {
  uint32_t magic{kMagic};
  uint32_t type{0};
  uint32_t size{0};
};

/** Unix-stream framed transport (POD payload = memcpy of IPC structs). */
class SocketTransport {
 public:
  SocketTransport() = default;
  ~SocketTransport();

  SocketTransport(const SocketTransport&) = delete;
  SocketTransport& operator=(const SocketTransport&) = delete;

  /** Peer (MCU sim): bind + listen + accept one client. */
  bool ListenAndAccept(const std::string& path = kDefaultSockPath);

  /** Gateway (AP): connect to peer. */
  bool Connect(const std::string& path = kDefaultSockPath);

  bool Send(MsgType type, const void* payload, uint32_t size);
  /** Blocking recv; returns false on disconnect / error. */
  bool Recv(MsgType* type, void* payload, uint32_t capacity, uint32_t* out_size);

  bool Ok() const { return fd_ >= 0; }
  void Close();

 private:
  int fd_{-1};
  int listen_fd_{-1};
  std::string path_;
  bool is_server_{false};
};

template <typename T>
bool SendPod(SocketTransport& t, MsgType type, const T& pod) {
  return t.Send(type, &pod, static_cast<uint32_t>(sizeof(T)));
}

template <typename T>
bool RecvPod(SocketTransport& t, MsgType expect, T* out) {
  MsgType got{};
  uint32_t n = 0;
  if (!t.Recv(&got, out, static_cast<uint32_t>(sizeof(T)), &n)) {
    return false;
  }
  return got == expect && n == sizeof(T);
}

}  // namespace gf_ara::com::binding::cross_domain_ipc
