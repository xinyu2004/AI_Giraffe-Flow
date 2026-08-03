#ifndef GF_ARA_DIAG_DOIP_SESSION_HPP
#define GF_ARA_DIAG_DOIP_SESSION_HPP

#include <gf_ara/core/result.hpp>

#include <atomic>
#include <cstdint>
#include <functional>
#include <string>
#include <thread>
#include <vector>

namespace gf_ara::diag {

/// UDS request handler: input UDS bytes → response UDS bytes (positive or NRC).
using UdsHandler =
    std::function<std::vector<std::uint8_t>(const std::vector<std::uint8_t>& uds)>;

struct DoipSessionConfig {
  std::uint16_t listen_port{13400};
  std::uint16_t entity_address{0x0E00};
  std::uint16_t expected_tester{0x0E80};
};

/// TCP DoIP entity (SIL / fake board). One client at a time.
class DoipTcpServer {
 public:
  DoipTcpServer();
  ~DoipTcpServer();

  DoipTcpServer(const DoipTcpServer&) = delete;
  DoipTcpServer& operator=(const DoipTcpServer&) = delete;

  void SetUdsHandler(UdsHandler handler);

  /// Bind + accept loop on background thread. Returns bound port (may be ephemeral if 0).
  gf_ara::core::Result<std::uint16_t> Start(DoipSessionConfig cfg);

  void Stop();

  [[nodiscard]] bool Running() const noexcept { return running_.load(); }
  [[nodiscard]] std::uint16_t Port() const noexcept { return port_; }

 private:
  void ThreadMain();
  void ServeClient(int client_fd);

  DoipSessionConfig cfg_{};
  UdsHandler uds_;
  std::atomic<bool> running_{false};
  std::atomic<bool> stop_{false};
  std::atomic<bool> client_busy_{false};
  int listen_fd_{-1};
  std::uint16_t port_{0};
  std::thread thr_;
};

/// Blocking TCP DoIP tester (host / GMT / smoke).
class DoipTcpClient {
 public:
  ~DoipTcpClient();

  gf_ara::core::Result<void> Connect(const std::string& host, std::uint16_t port,
                                     std::uint16_t tester_address = 0x0E80,
                                     std::uint16_t entity_address = 0x0E00);

  void Close();

  gf_ara::core::Result<void> RoutingActivation();

  /// Send UDS, wait for Diagnostic Message response (after ACK).
  gf_ara::core::Result<std::vector<std::uint8_t>> Transceive(
      const std::vector<std::uint8_t>& uds);

 private:
  gf_ara::core::Result<void> SendAll(const std::vector<std::uint8_t>& bytes);
  gf_ara::core::Result<std::vector<std::uint8_t>> RecvFramePayload(
      std::uint16_t expect_type);

  int fd_{-1};
  std::uint16_t tester_{0x0E80};
  std::uint16_t entity_{0x0E00};
  std::vector<std::uint8_t> rx_buf_;
};

/// Default in-process UDS: TesterPresent + RoutineControl OTA hooks via callback.
std::vector<std::uint8_t> DefaultUdsDispatch(
    const std::vector<std::uint8_t>& uds,
    const std::function<std::vector<std::uint8_t>(const std::vector<std::uint8_t>&)>&
        routine_hook = {});

}  // namespace gf_ara::diag

#endif
