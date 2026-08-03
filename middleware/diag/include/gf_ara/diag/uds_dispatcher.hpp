#ifndef GF_ARA_DIAG_UDS_DISPATCHER_HPP
#define GF_ARA_DIAG_UDS_DISPATCHER_HPP

#include <gf_ara/diag/security_plugin.h>

#include <chrono>
#include <cstdint>
#include <functional>
#include <fstream>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

namespace gf_ara::diag {

enum class UdsSession : std::uint8_t {
  kDefault = 0x01,
  kProgramming = 0x02,
  kExtended = 0x03,
};

/// Primary OTA byte-pipe (ISO 14229). DoIP (13400) is transport only.
enum class OtaTransferMode : std::uint8_t {
  kRequestFileTransfer = 0,  // 0x38 → 0x36 → 0x37 (DoIP default)
  kRequestDownload = 1,      // 0x34 → 0x36 → 0x37
  kRoutineSil = 2,           // 0x31 F100 shortcut (no byte pipe)
};

struct UdsConfig {
  bool iso_14229_uds{true};
  bool iso_13400_doip{false};
  std::string security_plugin_path;  // empty → built-in SIL stub (no dlopen)

  // Timing (ISO 14229). tester_present_period is client-side; enforced S3 is server-side.
  std::uint32_t s3_server_ms{5000};
  std::uint32_t tester_present_period_ms{2000};
  std::uint32_t p2_server_ms{50};
  std::uint32_t p2_star_server_ms{5000};
  /** After invalid 0x27 key: RequiredTimeDelayNotExpired (0x37) until this elapses. */
  std::uint32_t security_delay_ms{10000};

  OtaTransferMode ota_mode{OtaTransferMode::kRequestFileTransfer};
  bool ota_require_programming_session{true};
  bool ota_require_security{true};
  std::uint32_t ota_max_block_length{1024};
};

/// Forward complete UDS PDU to MCU (gateway). AP does not run ISO-TP.
using McuPduHandoff = std::function<bool(const std::vector<std::uint8_t>& uds_req,
                                         std::vector<std::uint8_t>& uds_resp)>;

/// Optional RoutineControl / OTA hook (wired to UCM by server binary).
using RoutineHook =
    std::function<std::vector<std::uint8_t>(const std::vector<std::uint8_t>& request)>;

/// Called after successful 0x37 (file/memory transfer complete) → UCM activate.
using TransferCompleteHook =
    std::function<bool(const std::string& artifact_path, std::uint64_t bytes)>;

/// ISO 14229 core dispatcher (NRC-complete for supported SIDs).
class UdsDispatcher {
 public:
  static UdsDispatcher& Instance();

  void Configure(UdsConfig cfg);
  [[nodiscard]] const UdsConfig& Config() const noexcept { return cfg_; }

  void SetMcuHandoff(McuPduHandoff handoff);
  void ClearMcuHandoff();
  void SetRoutineHook(RoutineHook hook);
  void SetTransferCompleteHook(TransferCompleteHook hook);

  /** Register DID value for 0x22 / 0x2E (in-memory). */
  void SetDid(std::uint16_t did, std::vector<std::uint8_t> data);
  [[nodiscard]] bool GetDid(std::uint16_t did, std::vector<std::uint8_t>& out);

  [[nodiscard]] UdsSession Session() const noexcept { return session_; }
  [[nodiscard]] bool SecurityUnlocked() const noexcept { return security_unlocked_; }

  /**
   * Process one UDS request → positive or NRC response.
   * Empty vector = suppress positive response (e.g. 0x3E with suppressPosRspBit).
   */
  [[nodiscard]] std::vector<std::uint8_t> Handle(const std::vector<std::uint8_t>& request);

  /** Call periodically (DoIP accept loop): enforce S3Server session timeout. */
  void TickTimeouts();

  /** Validate standards dependency: 13400 requires 14229. */
  [[nodiscard]] static bool StandardsValid(bool iso_14229, bool iso_13400) noexcept;

  [[nodiscard]] static OtaTransferMode ParseOtaMode(std::string_view s) noexcept;

 private:
  UdsDispatcher() = default;
  UdsConfig cfg_{};
  UdsSession session_{UdsSession::kDefault};
  bool security_unlocked_{false};
  std::uint8_t pending_seed_level_{0};
  std::vector<std::uint8_t> pending_seed_;
  std::unordered_map<std::uint16_t, std::vector<std::uint8_t>> dids_;
  McuPduHandoff mcu_;
  RoutineHook routine_;
  TransferCompleteHook xfer_done_;
  void* plugin_handle_{nullptr};
  const ::GfDiagSecPlugin* plugin_{nullptr};

  std::chrono::steady_clock::time_point last_activity_{};
  std::chrono::steady_clock::time_point security_delay_until_{};
  std::uint32_t security_fail_count_{0};
  bool transfer_active_{false};
  bool transfer_via_38_{false};
  std::uint8_t next_block_seq_{1};
  std::uint32_t max_block_len_{1024};
  std::uint64_t expected_size_{0};
  std::uint64_t received_size_{0};
  std::string transfer_path_;
  std::ofstream transfer_file_;

  bool LoadPlugin();
  void UnloadPlugin();
  void TouchActivity();
  void AbortTransfer();
  [[nodiscard]] bool OtaGateOk(std::uint8_t sid, std::vector<std::uint8_t>& nrc_out);
  std::vector<std::uint8_t> HandleSecurityAccess(const std::vector<std::uint8_t>& req);
  std::vector<std::uint8_t> HandleAuthentication(const std::vector<std::uint8_t>& req);
  std::vector<std::uint8_t> HandleRequestFileTransfer(const std::vector<std::uint8_t>& req);
  std::vector<std::uint8_t> HandleRequestDownload(const std::vector<std::uint8_t>& req);
  std::vector<std::uint8_t> HandleTransferData(const std::vector<std::uint8_t>& req);
  std::vector<std::uint8_t> HandleRequestTransferExit(const std::vector<std::uint8_t>& req);
};

}  // namespace gf_ara::diag

#endif
