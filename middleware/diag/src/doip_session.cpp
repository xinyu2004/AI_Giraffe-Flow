#include "gf_ara/diag/doip_session.hpp"

#include "gf_ara/diag/doip_proto.hpp"

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#include <cerrno>
#include <cstring>

namespace gf_ara::diag {
namespace {

constexpr std::uint8_t kRoutingOk = 0x10;

bool SetReuseAddr(int fd) {
  int yes = 1;
  return ::setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes)) == 0;
}

}  // namespace

std::vector<std::uint8_t> DefaultUdsDispatch(
    const std::vector<std::uint8_t>& uds,
    const std::function<std::vector<std::uint8_t>(const std::vector<std::uint8_t>&)>&
        routine_hook) {
  if (uds.empty()) {
    return {0x7F, 0x00, 0x13};  // incorrectMessageLength
  }
  if (uds[0] == 0x3E) {
    return {0x7E, uds.size() > 1 ? uds[1] : std::uint8_t{0}};
  }
  if (uds[0] == 0x31 && routine_hook) {
    return routine_hook(uds);
  }
  if (uds[0] == 0x31) {
    return {0x7F, 0x31, 0x11};  // serviceNotSupported (no hook)
  }
  return {0x7F, uds[0], 0x11};
}

DoipTcpServer::DoipTcpServer() = default;

DoipTcpServer::~DoipTcpServer() { Stop(); }

void DoipTcpServer::SetUdsHandler(UdsHandler handler) { uds_ = std::move(handler); }

gf_ara::core::Result<std::uint16_t> DoipTcpServer::Start(DoipSessionConfig cfg) {
  if (running_.load()) {
    return gf_ara::core::Result<std::uint16_t>::Err(gf_ara::core::ErrorCode::kBusy);
  }
  cfg_ = cfg;
  listen_fd_ = ::socket(AF_INET, SOCK_STREAM, 0);
  if (listen_fd_ < 0) {
    return gf_ara::core::Result<std::uint16_t>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  SetReuseAddr(listen_fd_);
  sockaddr_in addr{};
  addr.sin_family = AF_INET;
  addr.sin_addr.s_addr = htonl(INADDR_ANY);
  addr.sin_port = htons(cfg_.listen_port);
  if (::bind(listen_fd_, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0) {
    ::close(listen_fd_);
    listen_fd_ = -1;
    return gf_ara::core::Result<std::uint16_t>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  if (::listen(listen_fd_, 1) < 0) {
    ::close(listen_fd_);
    listen_fd_ = -1;
    return gf_ara::core::Result<std::uint16_t>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  sockaddr_in bound{};
  socklen_t blen = sizeof(bound);
  if (::getsockname(listen_fd_, reinterpret_cast<sockaddr*>(&bound), &blen) == 0) {
    port_ = ntohs(bound.sin_port);
  } else {
    port_ = cfg_.listen_port;
  }
  stop_ = false;
  running_ = true;
  thr_ = std::thread([this] { ThreadMain(); });
  return gf_ara::core::Result<std::uint16_t>::Ok(port_);
}

void DoipTcpServer::Stop() {
  stop_ = true;
  if (listen_fd_ >= 0) {
    ::shutdown(listen_fd_, SHUT_RDWR);
    ::close(listen_fd_);
    listen_fd_ = -1;
  }
  if (thr_.joinable()) {
    thr_.join();
  }
  running_ = false;
}

void DoipTcpServer::ThreadMain() {
  while (!stop_.load()) {
    sockaddr_in cli{};
    socklen_t clen = sizeof(cli);
    const int cfd = ::accept(listen_fd_, reinterpret_cast<sockaddr*>(&cli), &clen);
    if (cfd < 0) {
      if (stop_.load()) {
        break;
      }
      continue;
    }
    ServeClient(cfd);
    ::close(cfd);
  }
  running_ = false;
}

void DoipTcpServer::ServeClient(int client_fd) {
  std::vector<std::uint8_t> buf;
  buf.reserve(4096);
  std::uint8_t tmp[2048];
  bool activated = false;
  std::uint16_t tester = cfg_.expected_tester;

  while (!stop_.load()) {
    const ssize_t n = ::recv(client_fd, tmp, sizeof(tmp), 0);
    if (n <= 0) {
      break;
    }
    buf.insert(buf.end(), tmp, tmp + n);
    for (;;) {
      std::size_t consumed = 0;
      auto frame = TryDecodeDoipFrame(buf, consumed);
      if (!frame) {
        if (consumed > 0 && consumed <= buf.size()) {
          buf.erase(buf.begin(), buf.begin() + static_cast<std::ptrdiff_t>(consumed));
          continue;
        }
        break;
      }
      buf.erase(buf.begin(), buf.begin() + static_cast<std::ptrdiff_t>(consumed));

      if (frame->payload_type == DoipPayloadType::kRoutingActivationRequest) {
        if (frame->payload.size() >= 2) {
          tester = static_cast<std::uint16_t>((frame->payload[0] << 8) | frame->payload[1]);
        }
        auto resp =
            MakeRoutingActivationResponse(tester, cfg_.entity_address, kRoutingOk);
        (void)::send(client_fd, resp.data(), resp.size(), MSG_NOSIGNAL);
        activated = true;
        continue;
      }

      if (frame->payload_type == DoipPayloadType::kDiagnosticMessage) {
        if (!activated || frame->payload.size() < 5) {
          continue;
        }
        const auto src = static_cast<std::uint16_t>((frame->payload[0] << 8) |
                                                    frame->payload[1]);
        const auto tgt = static_cast<std::uint16_t>((frame->payload[2] << 8) |
                                                    frame->payload[3]);
        std::vector<std::uint8_t> uds(frame->payload.begin() + 4, frame->payload.end());
        auto ack = MakeDiagnosticMessageAck(cfg_.entity_address, src, 0x00);
        (void)::send(client_fd, ack.data(), ack.size(), MSG_NOSIGNAL);

        std::vector<std::uint8_t> uds_resp;
        if (uds_) {
          uds_resp = uds_(uds);
        } else {
          uds_resp = DefaultUdsDispatch(uds);
        }
        auto msg = MakeDiagnosticMessage(cfg_.entity_address, src, uds_resp);
        (void)::send(client_fd, msg.data(), msg.size(), MSG_NOSIGNAL);
        (void)tgt;
        continue;
      }
    }
  }
}

DoipTcpClient::~DoipTcpClient() { Close(); }

gf_ara::core::Result<void> DoipTcpClient::Connect(const std::string& host,
                                                  std::uint16_t port,
                                                  std::uint16_t tester_address,
                                                  std::uint16_t entity_address) {
  Close();
  tester_ = tester_address;
  entity_ = entity_address;
  fd_ = ::socket(AF_INET, SOCK_STREAM, 0);
  if (fd_ < 0) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  sockaddr_in addr{};
  addr.sin_family = AF_INET;
  addr.sin_port = htons(port);
  if (::inet_pton(AF_INET, host.c_str(), &addr.sin_addr) != 1) {
    Close();
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kInvalidArgument);
  }
  if (::connect(fd_, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0) {
    Close();
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  return gf_ara::core::Result<void>::Ok();
}

void DoipTcpClient::Close() {
  if (fd_ >= 0) {
    ::close(fd_);
    fd_ = -1;
  }
  rx_buf_.clear();
}

gf_ara::core::Result<void> DoipTcpClient::SendAll(const std::vector<std::uint8_t>& bytes) {
  if (fd_ < 0) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  std::size_t off = 0;
  while (off < bytes.size()) {
    const ssize_t n =
        ::send(fd_, bytes.data() + off, bytes.size() - off, MSG_NOSIGNAL);
    if (n <= 0) {
      return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
    }
    off += static_cast<std::size_t>(n);
  }
  return gf_ara::core::Result<void>::Ok();
}

gf_ara::core::Result<std::vector<std::uint8_t>> DoipTcpClient::RecvFramePayload(
    std::uint16_t expect_type) {
  std::uint8_t tmp[2048];
  for (;;) {
    std::size_t consumed = 0;
    auto frame = TryDecodeDoipFrame(rx_buf_, consumed);
    if (frame) {
      rx_buf_.erase(rx_buf_.begin(),
                    rx_buf_.begin() + static_cast<std::ptrdiff_t>(consumed));
      if (static_cast<std::uint16_t>(frame->payload_type) != expect_type) {
        // skip unexpected; keep reading
        continue;
      }
      return gf_ara::core::Result<std::vector<std::uint8_t>>::Ok(std::move(frame->payload));
    }
    if (consumed > 0 && consumed <= rx_buf_.size()) {
      rx_buf_.erase(rx_buf_.begin(),
                    rx_buf_.begin() + static_cast<std::ptrdiff_t>(consumed));
      continue;
    }
    const ssize_t n = ::recv(fd_, tmp, sizeof(tmp), 0);
    if (n <= 0) {
      return gf_ara::core::Result<std::vector<std::uint8_t>>::Err(
          gf_ara::core::ErrorCode::kNotAvailable);
    }
    rx_buf_.insert(rx_buf_.end(), tmp, tmp + n);
  }
}

gf_ara::core::Result<void> DoipTcpClient::RoutingActivation() {
  auto req = MakeRoutingActivationRequest(tester_);
  if (!SendAll(req)) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  auto payload =
      RecvFramePayload(static_cast<std::uint16_t>(DoipPayloadType::kRoutingActivationResponse));
  if (!payload) {
    return gf_ara::core::Result<void>::Err(payload.Error());
  }
  if (payload.Value().size() < 5 || payload.Value()[4] != kRoutingOk) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  return gf_ara::core::Result<void>::Ok();
}

gf_ara::core::Result<std::vector<std::uint8_t>> DoipTcpClient::Transceive(
    const std::vector<std::uint8_t>& uds) {
  auto req = MakeDiagnosticMessage(tester_, entity_, uds);
  if (!SendAll(req)) {
    return gf_ara::core::Result<std::vector<std::uint8_t>>::Err(
        gf_ara::core::ErrorCode::kNotAvailable);
  }
  // ACK then diagnostic response
  auto ack =
      RecvFramePayload(static_cast<std::uint16_t>(DoipPayloadType::kDiagnosticMessagePositiveAck));
  if (!ack) {
    return gf_ara::core::Result<std::vector<std::uint8_t>>::Err(ack.Error());
  }
  auto resp =
      RecvFramePayload(static_cast<std::uint16_t>(DoipPayloadType::kDiagnosticMessage));
  if (!resp) {
    return gf_ara::core::Result<std::vector<std::uint8_t>>::Err(resp.Error());
  }
  if (resp.Value().size() < 4) {
    return gf_ara::core::Result<std::vector<std::uint8_t>>::Err(
        gf_ara::core::ErrorCode::kNotAvailable);
  }
  return gf_ara::core::Result<std::vector<std::uint8_t>>::Ok(
      std::vector<std::uint8_t>(resp.Value().begin() + 4, resp.Value().end()));
}

}  // namespace gf_ara::diag
