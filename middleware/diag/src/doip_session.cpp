#include "gf_ara/diag/doip_session.hpp"

#include "gf_ara/diag/doip_proto.hpp"
#include "gf_ara/diag/uds_dispatcher.hpp"

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <unistd.h>

#include <cerrno>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>

namespace gf_ara::diag {
namespace {

constexpr std::uint8_t kRoutingOk = 0x10;

bool SetReuseAddr(int fd) {
  int yes = 1;
  return ::setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes)) == 0;
}

const char* UdsSidName(std::uint8_t sid) {
  switch (sid) {
    case 0x10:
      return "DiagnosticSessionControl";
    case 0x11:
      return "ECUReset";
    case 0x27:
      return "SecurityAccess";
    case 0x29:
      return "Authentication";
    case 0x31:
      return "RoutineControl";
    case 0x34:
      return "RequestDownload";
    case 0x36:
      return "TransferData";
    case 0x37:
      return "RequestTransferExit";
    case 0x38:
      return "RequestFileTransfer";
    case 0x3E:
      return "TesterPresent";
    default:
      return "SID";
  }
}

std::string HexBytes(const std::vector<std::uint8_t>& v) {
  std::ostringstream oss;
  oss << std::hex << std::setfill('0');
  for (auto b : v) {
    oss << std::setw(2) << static_cast<unsigned>(b);
  }
  return oss.str();
}

void LogUdsStep(const std::vector<std::uint8_t>& req,
                const std::vector<std::uint8_t>& resp) {
  if (req.empty()) {
    return;
  }
  const bool ok = !resp.empty() && resp[0] != 0x7F;
  std::cout << "[DoIP] UDS 0x" << std::hex << std::setfill('0') << std::setw(2)
            << static_cast<unsigned>(req[0]) << std::dec << ' ' << UdsSidName(req[0])
            << "  req=" << HexBytes(req) << "  resp=" << HexBytes(resp) << "  ["
            << (ok ? "OK" : "NRC") << "]\n"
            << std::flush;
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
    char peer_ip[INET_ADDRSTRLEN] = "?";
    if (cli.sin_family == AF_INET) {
      (void)::inet_ntop(AF_INET, &cli.sin_addr, peer_ip, sizeof(peer_ip));
    }
    const auto peer_port = static_cast<unsigned>(::ntohs(cli.sin_port));
    bool expected = false;
    if (!client_busy_.compare_exchange_strong(expected, true)) {
      std::cout << "[DoIP] reject second TCP client (single-session entity) peer="
                << peer_ip << ':' << peer_port << '\n'
                << std::flush;
      ::close(cfd);
      continue;
    }
    std::cout << "[DoIP] TCP client connected peer=" << peer_ip << ':' << peer_port
              << '\n'
              << std::flush;
    ServeClient(cfd);
    std::cout << "[DoIP] TCP client disconnected peer=" << peer_ip << ':' << peer_port
              << '\n'
              << std::flush;
    ::close(cfd);
    client_busy_ = false;
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
    // Poll so S3Server can fire without waiting forever on recv
    fd_set rfds;
    FD_ZERO(&rfds);
    FD_SET(client_fd, &rfds);
    timeval tv{};
    tv.tv_sec = 0;
    tv.tv_usec = 200 * 1000;
    const int sel = ::select(client_fd + 1, &rfds, nullptr, nullptr, &tv);
    gf_ara::diag::UdsDispatcher::Instance().TickTimeouts();
    if (sel == 0) {
      continue;
    }
    if (sel < 0) {
      if (stop_.load()) {
        break;
      }
      continue;
    }
    const ssize_t n = ::recv(client_fd, tmp, sizeof(tmp), 0);
    if (n <= 0) {
      break;
    }
    const auto rx_cap = cfg_.rx_max_bytes == 0 ? 65536u : cfg_.rx_max_bytes;
    if (buf.size() + static_cast<std::size_t>(n) > rx_cap) {
      break;  // BL-MEM-BOUND: close client on oversize stream
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
        std::cout << "[DoIP] RoutingActivation tester=0x" << std::hex << std::setfill('0')
                  << std::setw(4) << tester << std::dec << "  [OK]\n"
                  << std::flush;
        continue;
      }

      if (frame->payload_type == DoipPayloadType::kAliveCheckRequest) {
        auto resp = MakeAliveCheckResponse(cfg_.entity_address);
        (void)::send(client_fd, resp.data(), resp.size(), MSG_NOSIGNAL);
        std::cout << "[DoIP] AliveCheck → response entity=0x" << std::hex << std::setfill('0')
                  << std::setw(4) << cfg_.entity_address << std::dec << "\n"
                  << std::flush;
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
        if (tgt != cfg_.entity_address) {
          // 0x02 = unknown target address (ISO 13400-2)
          auto nack = MakeDiagnosticMessageNack(cfg_.entity_address, src, 0x02);
          (void)::send(client_fd, nack.data(), nack.size(), MSG_NOSIGNAL);
          std::cout << "[DoIP] NACK unknown target=0x" << std::hex << tgt
                    << " (entity=0x" << cfg_.entity_address << ")\n"
                    << std::dec << std::flush;
          continue;
        }
        std::vector<std::uint8_t> uds(frame->payload.begin() + 4, frame->payload.end());
        auto ack = MakeDiagnosticMessageAck(cfg_.entity_address, src, 0x00);
        (void)::send(client_fd, ack.data(), ack.size(), MSG_NOSIGNAL);

        std::vector<std::uint8_t> uds_resp;
        if (uds_) {
          uds_resp = uds_(uds);
        } else {
          uds_resp = DefaultUdsDispatch(uds);
        }
        if (!uds.empty() && !(uds[0] == 0x3E && uds_resp.empty())) {
          LogUdsStep(uds, uds_resp);
        }
        if (!uds_resp.empty()) {
          auto msg = MakeDiagnosticMessage(cfg_.entity_address, src, uds_resp);
          (void)::send(client_fd, msg.data(), msg.size(), MSG_NOSIGNAL);
        }
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
    if (rx_buf_.size() + static_cast<std::size_t>(n) > rx_max_bytes_) {
      return gf_ara::core::Result<std::vector<std::uint8_t>>::Err(
          gf_ara::core::ErrorCode::kInvalidArgument);
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
