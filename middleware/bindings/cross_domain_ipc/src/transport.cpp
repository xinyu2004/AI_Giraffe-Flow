#include "gf_ara/com/binding/cross_domain_ipc/transport.hpp"

#include <cerrno>
#include <cstring>
#include <iostream>
#include <unistd.h>

#include <sys/socket.h>
#include <sys/un.h>

namespace gf_ara::com::binding::cross_domain_ipc {
namespace {

bool WriteAll(int fd, const void* buf, size_t n) {
  const auto* p = static_cast<const uint8_t*>(buf);
  size_t left = n;
  while (left > 0) {
    const ssize_t w = ::write(fd, p, left);
    if (w < 0) {
      if (errno == EINTR) {
        continue;
      }
      return false;
    }
    if (w == 0) {
      return false;
    }
    p += static_cast<size_t>(w);
    left -= static_cast<size_t>(w);
  }
  return true;
}

bool ReadAll(int fd, void* buf, size_t n) {
  auto* p = static_cast<uint8_t*>(buf);
  size_t left = n;
  while (left > 0) {
    const ssize_t r = ::read(fd, p, left);
    if (r < 0) {
      if (errno == EINTR) {
        continue;
      }
      return false;
    }
    if (r == 0) {
      return false;
    }
    p += static_cast<size_t>(r);
    left -= static_cast<size_t>(r);
  }
  return true;
}

}  // namespace

SocketTransport::~SocketTransport() { Close(); }

void SocketTransport::Close() {
  if (fd_ >= 0) {
    ::close(fd_);
    fd_ = -1;
  }
  if (listen_fd_ >= 0) {
    ::close(listen_fd_);
    listen_fd_ = -1;
  }
  if (is_server_ && !path_.empty()) {
    ::unlink(path_.c_str());
  }
  path_.clear();
  is_server_ = false;
}

bool SocketTransport::ListenAndAccept(const std::string& path) {
  Close();
  path_ = path;
  is_server_ = true;
  ::unlink(path_.c_str());

  listen_fd_ = ::socket(AF_UNIX, SOCK_STREAM, 0);
  if (listen_fd_ < 0) {
    std::cerr << "cross_domain_ipc: socket failed: " << std::strerror(errno) << "\n";
    return false;
  }

  sockaddr_un addr{};
  addr.sun_family = AF_UNIX;
  if (path_.size() >= sizeof(addr.sun_path)) {
    std::cerr << "cross_domain_ipc: path too long\n";
    Close();
    return false;
  }
  std::strncpy(addr.sun_path, path_.c_str(), sizeof(addr.sun_path) - 1);

  if (::bind(listen_fd_, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0) {
    std::cerr << "cross_domain_ipc: bind failed: " << std::strerror(errno) << "\n";
    Close();
    return false;
  }
  if (::listen(listen_fd_, 1) < 0) {
    std::cerr << "cross_domain_ipc: listen failed: " << std::strerror(errno) << "\n";
    Close();
    return false;
  }

  fd_ = ::accept(listen_fd_, nullptr, nullptr);
  if (fd_ < 0) {
    std::cerr << "cross_domain_ipc: accept failed: " << std::strerror(errno) << "\n";
    Close();
    return false;
  }
  ::close(listen_fd_);
  listen_fd_ = -1;
  return true;
}

bool SocketTransport::Connect(const std::string& path) {
  Close();
  path_ = path;
  is_server_ = false;

  fd_ = ::socket(AF_UNIX, SOCK_STREAM, 0);
  if (fd_ < 0) {
    std::cerr << "cross_domain_ipc: socket failed: " << std::strerror(errno) << "\n";
    return false;
  }

  sockaddr_un addr{};
  addr.sun_family = AF_UNIX;
  if (path_.size() >= sizeof(addr.sun_path)) {
    std::cerr << "cross_domain_ipc: path too long\n";
    Close();
    return false;
  }
  std::strncpy(addr.sun_path, path_.c_str(), sizeof(addr.sun_path) - 1);

  if (::connect(fd_, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0) {
    std::cerr << "cross_domain_ipc: connect failed: " << std::strerror(errno) << "\n";
    Close();
    return false;
  }
  return true;
}

bool SocketTransport::Send(MsgType type, const void* payload, uint32_t size) {
  if (fd_ < 0) {
    return false;
  }
  FrameHeader hdr{};
  hdr.magic = kMagic;
  hdr.type = static_cast<uint32_t>(type);
  hdr.size = size;
  if (!WriteAll(fd_, &hdr, sizeof(hdr))) {
    return false;
  }
  if (size == 0) {
    return true;
  }
  return WriteAll(fd_, payload, size);
}

bool SocketTransport::Recv(MsgType* type, void* payload, uint32_t capacity, uint32_t* out_size) {
  if (fd_ < 0 || type == nullptr || out_size == nullptr) {
    return false;
  }
  FrameHeader hdr{};
  if (!ReadAll(fd_, &hdr, sizeof(hdr))) {
    return false;
  }
  if (hdr.magic != kMagic) {
    std::cerr << "cross_domain_ipc: bad magic\n";
    return false;
  }
  if (hdr.size > capacity) {
    std::cerr << "cross_domain_ipc: payload too large (" << hdr.size << " > " << capacity
              << ")\n";
    return false;
  }
  if (hdr.size > 0 && !ReadAll(fd_, payload, hdr.size)) {
    return false;
  }
  *type = static_cast<MsgType>(hdr.type);
  *out_size = hdr.size;
  return true;
}

}  // namespace gf_ara::com::binding::cross_domain_ipc
