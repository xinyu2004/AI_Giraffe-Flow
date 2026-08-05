#include "gf_ara/diag/uds_dispatcher.hpp"

#include "gf_ara/diag/security_plugin.h"
#include "gf_ara/diag/uds_nrc.hpp"

#include <gf_ara/collector/event_collector.hpp>

#include <dlfcn.h>

#include <cstring>
#include <filesystem>
#include <iostream>
#include <mutex>
#include <sstream>

namespace gf_ara::diag {
namespace {

std::mutex& Mu() {
  static std::mutex m;
  return m;
}

std::uint16_t Be16(const std::uint8_t* p) {
  return static_cast<std::uint16_t>((p[0] << 8) | p[1]);
}

void PutBe32(std::vector<std::uint8_t>& out, std::uint32_t v) {
  out.push_back(static_cast<std::uint8_t>((v >> 24) & 0xFF));
  out.push_back(static_cast<std::uint8_t>((v >> 16) & 0xFF));
  out.push_back(static_cast<std::uint8_t>((v >> 8) & 0xFF));
  out.push_back(static_cast<std::uint8_t>(v & 0xFF));
}

// Built-in SIL seed/key when no .so loaded (level 1: seed AA55 → key 55AA)
int SilRequestSeed(uint8_t level, uint8_t* seed, size_t* seed_len, size_t seed_cap) {
  if (level == 0 || seed_cap < 2) {
    return static_cast<int>(UdsNrc::kRequestOutOfRange);
  }
  seed[0] = 0xAA;
  seed[1] = 0x55;
  *seed_len = 2;
  (void)level;
  return 0;
}

int SilVerifyKey(uint8_t level, const uint8_t* key, size_t key_len) {
  (void)level;
  if (key_len < 2) {
    return static_cast<int>(UdsNrc::kIncorrectMessageLength);
  }
  if (key[0] == 0x55 && key[1] == 0xAA) {
    return 0;
  }
  return static_cast<int>(UdsNrc::kInvalidKey);
}

int SilAuthenticate(const uint8_t* req, size_t req_len, uint8_t* resp, size_t* resp_len,
                    size_t resp_cap) {
  (void)req;
  if (req_len < 2) {
    return static_cast<int>(UdsNrc::kIncorrectMessageLength);
  }
  if (resp_cap < 2) {
    return static_cast<int>(UdsNrc::kGeneralReject);
  }
  resp[0] = 0x69;
  resp[1] = req[1];
  *resp_len = 2;
  return 0;
}

const GfDiagSecPlugin kSilPlugin{
    GF_DIAG_SEC_ABI_VERSION,
    SilRequestSeed,
    SilVerifyKey,
    SilAuthenticate,
};

}  // namespace

UdsDispatcher& UdsDispatcher::Instance() {
  static UdsDispatcher d;
  return d;
}

bool UdsDispatcher::StandardsValid(bool iso_14229, bool iso_13400) noexcept {
  if (iso_13400 && !iso_14229) {
    return false;
  }
  return true;
}

OtaTransferMode UdsDispatcher::ParseOtaMode(std::string_view s) noexcept {
  if (s == "request_download" || s == "0x34" || s == "34") {
    return OtaTransferMode::kRequestDownload;
  }
  if (s == "routine_sil" || s == "0x31" || s == "31" || s == "sil") {
    return OtaTransferMode::kRoutineSil;
  }
  return OtaTransferMode::kRequestFileTransfer;
}

void UdsDispatcher::Configure(UdsConfig cfg) {
  std::lock_guard lock(Mu());
  UnloadPlugin();
  AbortTransfer();
  cfg_ = std::move(cfg);
  if (cfg_.ota_max_block_length < 8) {
    cfg_.ota_max_block_length = 8;
  }
  if (cfg_.tester_present_period_ms >= cfg_.s3_server_ms && cfg_.s3_server_ms > 0) {
    std::cerr << "diag: warn tester_present_period_ms (" << cfg_.tester_present_period_ms
              << ") >= s3_server_ms (" << cfg_.s3_server_ms << ") — session may drop\n";
  }
  session_ = UdsSession::kDefault;
  security_unlocked_ = false;
  pending_seed_.clear();
  security_fail_count_ = 0;
  security_delay_until_ = {};
  last_activity_ = std::chrono::steady_clock::now();
  if (!cfg_.security_plugin_path.empty()) {
    (void)LoadPlugin();
  } else {
    plugin_ = &kSilPlugin;
  }
}

void UdsDispatcher::SetMcuHandoff(McuPduHandoff handoff) {
  std::lock_guard lock(Mu());
  mcu_ = std::move(handoff);
}

void UdsDispatcher::ClearMcuHandoff() {
  std::lock_guard lock(Mu());
  mcu_ = nullptr;
}

void UdsDispatcher::SetRoutineHook(RoutineHook hook) {
  std::lock_guard lock(Mu());
  routine_ = std::move(hook);
}

void UdsDispatcher::SetTransferCompleteHook(TransferCompleteHook hook) {
  std::lock_guard lock(Mu());
  xfer_done_ = std::move(hook);
}

void UdsDispatcher::ConfigureDidBounds(std::uint32_t max_entries,
                                       std::uint32_t max_payload) {
  std::lock_guard lock(Mu());
  did_max_entries_ = max_entries == 0 ? 256 : max_entries;
  did_max_payload_ = max_payload == 0 ? 4096 : max_payload;
}

void UdsDispatcher::SetDid(std::uint16_t did, std::vector<std::uint8_t> data) {
  std::lock_guard lock(Mu());
  if (data.size() > did_max_payload_) {
    return;
  }
  if (dids_.find(did) == dids_.end() && dids_.size() >= did_max_entries_) {
    return;
  }
  dids_[did] = std::move(data);
}

bool UdsDispatcher::GetDid(std::uint16_t did, std::vector<std::uint8_t>& out) {
  std::lock_guard lock(Mu());
  const auto it = dids_.find(did);
  if (it == dids_.end()) {
    return false;
  }
  out = it->second;
  return true;
}

bool UdsDispatcher::LoadPlugin() {
  UnloadPlugin();
  plugin_handle_ = ::dlopen(cfg_.security_plugin_path.c_str(), RTLD_NOW);
  if (!plugin_handle_) {
    std::cerr << "diag: dlopen failed " << cfg_.security_plugin_path << " : " << dlerror()
              << " — using SIL stub\n";
    plugin_ = &kSilPlugin;
    return false;
  }
  auto sym = reinterpret_cast<GfDiagSecGetPluginFn>(::dlsym(plugin_handle_, GF_DIAG_SEC_GET_PLUGIN));
  if (!sym) {
    std::cerr << "diag: missing " << GF_DIAG_SEC_GET_PLUGIN << " — using SIL stub\n";
    ::dlclose(plugin_handle_);
    plugin_handle_ = nullptr;
    plugin_ = &kSilPlugin;
    return false;
  }
  plugin_ = sym();
  if (!plugin_ || plugin_->abi_version != GF_DIAG_SEC_ABI_VERSION) {
    std::cerr << "diag: bad plugin ABI — using SIL stub\n";
    ::dlclose(plugin_handle_);
    plugin_handle_ = nullptr;
    plugin_ = &kSilPlugin;
    return false;
  }
  return true;
}

void UdsDispatcher::UnloadPlugin() {
  if (plugin_handle_) {
    ::dlclose(plugin_handle_);
    plugin_handle_ = nullptr;
  }
  plugin_ = nullptr;
}

void UdsDispatcher::TouchActivity() {
  last_activity_ = std::chrono::steady_clock::now();
}

void UdsDispatcher::AbortTransfer() {
  if (transfer_file_.is_open()) {
    transfer_file_.close();
  }
  if (!transfer_path_.empty() && transfer_active_) {
    std::error_code ec;
    std::filesystem::remove(transfer_path_, ec);
  }
  transfer_active_ = false;
  transfer_via_38_ = false;
  next_block_seq_ = 1;
  expected_size_ = 0;
  received_size_ = 0;
  transfer_path_.clear();
}

void UdsDispatcher::TickTimeouts() {
  std::lock_guard lock(Mu());
  if (session_ == UdsSession::kDefault) {
    return;
  }
  if (cfg_.s3_server_ms == 0) {
    return;
  }
  const auto now = std::chrono::steady_clock::now();
  const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(now - last_activity_).count();
  if (ms < static_cast<std::chrono::milliseconds::rep>(cfg_.s3_server_ms)) {
    return;
  }
  std::cerr << "diag: S3Server timeout (" << cfg_.s3_server_ms
            << " ms) — session → Default, security locked, transfer aborted\n";
  session_ = UdsSession::kDefault;
  security_unlocked_ = false;
  pending_seed_.clear();
  AbortTransfer();
}

bool UdsDispatcher::OtaGateOk(std::uint8_t sid, std::vector<std::uint8_t>& nrc_out) {
  if (cfg_.ota_require_programming_session && session_ != UdsSession::kProgramming) {
    nrc_out = MakeNrc(sid, UdsNrc::kServiceNotSupportedInActiveSession);
    return false;
  }
  if (cfg_.ota_require_security && !security_unlocked_) {
    nrc_out = MakeNrc(sid, UdsNrc::kSecurityAccessDenied);
    return false;
  }
  return true;
}

std::vector<std::uint8_t> UdsDispatcher::HandleSecurityAccess(
    const std::vector<std::uint8_t>& req) {
  if (req.size() < 2) {
    return MakeNrc(0x27, UdsNrc::kIncorrectMessageLength);
  }
  const auto now = std::chrono::steady_clock::now();
  if (security_delay_until_.time_since_epoch().count() != 0 && now < security_delay_until_) {
    return MakeNrc(0x27, UdsNrc::kRequiredTimeDelayNotExpired);
  }
  if (!plugin_) {
    plugin_ = &kSilPlugin;
  }
  const auto sub = req[1];
  if ((sub & 0x7F) % 2 == 1) {
    const auto level = static_cast<std::uint8_t>((sub + 1) / 2);
    uint8_t seed[16];
    size_t slen = 0;
    const int rc = plugin_->request_seed(level, seed, &slen, sizeof(seed));
    if (rc != 0) {
      return MakeNrc(0x27, static_cast<UdsNrc>(rc));
    }
    pending_seed_level_ = level;
    pending_seed_.assign(seed, seed + slen);
    std::vector<std::uint8_t> out = {0x67, sub};
    out.insert(out.end(), pending_seed_.begin(), pending_seed_.end());
    return out;
  }
  const auto level = static_cast<std::uint8_t>(sub / 2);
  if (level != pending_seed_level_ || pending_seed_.empty()) {
    return MakeNrc(0x27, UdsNrc::kRequestSequenceError);
  }
  const int rc = plugin_->verify_key(level, req.data() + 2, req.size() - 2);
  pending_seed_.clear();
  pending_seed_level_ = 0;
  if (rc != 0) {
    security_unlocked_ = false;
    ++security_fail_count_;
    if (cfg_.security_delay_ms > 0) {
      security_delay_until_ =
          now + std::chrono::milliseconds(cfg_.security_delay_ms);
      std::cerr << "diag: SecurityAccess invalid key — delay "
                << cfg_.security_delay_ms << " ms (fails=" << security_fail_count_
                << ")\n";
    }
    return MakeNrc(0x27, static_cast<UdsNrc>(rc));
  }
  security_unlocked_ = true;
  security_fail_count_ = 0;
  security_delay_until_ = {};
  return {0x67, sub};
}

std::vector<std::uint8_t> UdsDispatcher::HandleAuthentication(
    const std::vector<std::uint8_t>& req) {
  if (req.size() < 2) {
    return MakeNrc(0x29, UdsNrc::kIncorrectMessageLength);
  }
  if (!plugin_ || !plugin_->authenticate) {
    return MakeNrc(0x29, UdsNrc::kServiceNotSupported);
  }
  uint8_t resp[64];
  size_t rlen = 0;
  const int rc = plugin_->authenticate(req.data(), req.size(), resp, &rlen, sizeof(resp));
  if (rc != 0) {
    return MakeNrc(0x29, static_cast<UdsNrc>(rc));
  }
  return std::vector<std::uint8_t>(resp, resp + rlen);
}

std::vector<std::uint8_t> UdsDispatcher::HandleRequestFileTransfer(
    const std::vector<std::uint8_t>& req) {
  // 0x38 | mode | pathLen | path… | dataFormatId | sizeLen | sizeUncomp | sizeComp
  if (cfg_.ota_mode != OtaTransferMode::kRequestFileTransfer) {
    return MakeNrc(0x38, UdsNrc::kServiceNotSupported);
  }
  std::vector<std::uint8_t> gate;
  if (!OtaGateOk(0x38, gate)) {
    return gate;
  }
  if (req.size() < 4) {
    return MakeNrc(0x38, UdsNrc::kIncorrectMessageLength);
  }
  const auto mode = req[1];
  if (mode != 0x01 && mode != 0x03) {  // AddFile / ReplaceFile
    return MakeNrc(0x38, UdsNrc::kSubFunctionNotSupported);
  }
  const auto path_len = static_cast<std::size_t>(req[2]);
  if (req.size() < 3 + path_len + 2) {
    return MakeNrc(0x38, UdsNrc::kIncorrectMessageLength);
  }
  std::string path(reinterpret_cast<const char*>(req.data() + 3), path_len);
  const std::size_t df_i = 3 + path_len;
  const auto data_fmt = req[df_i];
  const auto size_len = static_cast<std::size_t>(req[df_i + 1]);
  if (size_len == 0 || size_len > 8 || req.size() < df_i + 2 + 2 * size_len) {
    return MakeNrc(0x38, UdsNrc::kIncorrectMessageLength);
  }
  std::uint64_t uncomp = 0;
  for (std::size_t i = 0; i < size_len; ++i) {
    uncomp = (uncomp << 8) | req[df_i + 2 + i];
  }
  (void)data_fmt;

  AbortTransfer();
  // Stage under /tmp — path from tester is the logical name; bytes arrive via 0x36
  const auto base = std::filesystem::path(path).filename().string();
  transfer_path_ = "/tmp/gf_ota_" + (base.empty() ? "pkg.bin" : base);
  transfer_file_.open(transfer_path_, std::ios::binary | std::ios::trunc);
  if (!transfer_file_) {
    transfer_path_.clear();
    return MakeNrc(0x38, UdsNrc::kGeneralReject);
  }
  transfer_active_ = true;
  transfer_via_38_ = true;
  next_block_seq_ = 1;
  expected_size_ = uncomp;
  received_size_ = 0;
  max_block_len_ = cfg_.ota_max_block_length;

  // 0x78 | mode | lengthFormatId(0x40→4-byte maxBlock) | maxBlock | dataFormatId
  std::vector<std::uint8_t> out = {0x78, mode, 0x40};
  PutBe32(out, max_block_len_);
  out.push_back(data_fmt);
  return out;
}

std::vector<std::uint8_t> UdsDispatcher::HandleRequestDownload(
    const std::vector<std::uint8_t>& req) {
  if (cfg_.ota_mode != OtaTransferMode::kRequestDownload) {
    return MakeNrc(0x34, UdsNrc::kServiceNotSupported);
  }
  std::vector<std::uint8_t> gate;
  if (!OtaGateOk(0x34, gate)) {
    return gate;
  }
  // Minimal: dataFormatId | alfi | address… | size…
  if (req.size() < 5) {
    return MakeNrc(0x34, UdsNrc::kIncorrectMessageLength);
  }
  const auto alfi = req[2];
  const auto addr_len = static_cast<std::size_t>((alfi >> 4) & 0x0F);
  const auto size_len = static_cast<std::size_t>(alfi & 0x0F);
  if (addr_len == 0 || size_len == 0 || req.size() < 3 + addr_len + size_len) {
    return MakeNrc(0x34, UdsNrc::kIncorrectMessageLength);
  }
  std::uint64_t mem_size = 0;
  for (std::size_t i = 0; i < size_len; ++i) {
    mem_size = (mem_size << 8) | req[3 + addr_len + i];
  }

  AbortTransfer();
  transfer_path_ = "/tmp/gf_ota_download.bin";
  transfer_file_.open(transfer_path_, std::ios::binary | std::ios::trunc);
  if (!transfer_file_) {
    transfer_path_.clear();
    return MakeNrc(0x34, UdsNrc::kGeneralReject);
  }
  transfer_active_ = true;
  transfer_via_38_ = false;
  next_block_seq_ = 1;
  expected_size_ = mem_size;
  received_size_ = 0;
  max_block_len_ = cfg_.ota_max_block_length;

  std::vector<std::uint8_t> out = {0x74, 0x40};
  PutBe32(out, max_block_len_);
  return out;
}

std::vector<std::uint8_t> UdsDispatcher::HandleTransferData(
    const std::vector<std::uint8_t>& req) {
  if (!transfer_active_ || !transfer_file_.is_open()) {
    return MakeNrc(0x36, UdsNrc::kRequestSequenceError);
  }
  if (req.size() < 2) {
    return MakeNrc(0x36, UdsNrc::kIncorrectMessageLength);
  }
  const auto seq = req[1];
  if (seq != next_block_seq_) {
    return MakeNrc(0x36, UdsNrc::kWrongBlockSequenceCounter);
  }
  const auto* data = req.data() + 2;
  const auto len = req.size() - 2;
  if (len > max_block_len_) {
    return MakeNrc(0x36, UdsNrc::kIncorrectMessageLength);
  }
  transfer_file_.write(reinterpret_cast<const char*>(data), static_cast<std::streamsize>(len));
  if (!transfer_file_) {
    AbortTransfer();
    return MakeNrc(0x36, UdsNrc::kGeneralReject);
  }
  received_size_ += len;
  next_block_seq_ = static_cast<std::uint8_t>(next_block_seq_ == 0xFF ? 0 : next_block_seq_ + 1);
  return {0x76, seq};
}

std::vector<std::uint8_t> UdsDispatcher::HandleRequestTransferExit(
    const std::vector<std::uint8_t>& req) {
  (void)req;
  if (!transfer_active_) {
    return MakeNrc(0x37, UdsNrc::kRequestSequenceError);
  }
  if (transfer_file_.is_open()) {
    transfer_file_.close();
  }
  if (expected_size_ > 0 && received_size_ != expected_size_) {
    AbortTransfer();
    return MakeNrc(0x37, UdsNrc::kGeneralReject);
  }
  const std::string path = transfer_path_;
  const std::uint64_t bytes = received_size_;
  transfer_active_ = false;
  transfer_path_.clear();

  bool ok = true;
  if (xfer_done_) {
    ok = xfer_done_(path, bytes);
  }
  if (!ok) {
    return MakeNrc(0x37, UdsNrc::kGeneralProgrammingFailure);
  }
  return {0x77};
}

std::vector<std::uint8_t> UdsDispatcher::Handle(const std::vector<std::uint8_t>& request) {
  std::lock_guard lock(Mu());
  const auto t0 = std::chrono::steady_clock::now();
  if (!cfg_.iso_14229_uds) {
    return MakeNrc(request.empty() ? 0x00 : request[0], UdsNrc::kServiceNotSupported);
  }
  if (request.empty()) {
    return MakeNrc(0x00, UdsNrc::kIncorrectMessageLength);
  }

  TouchActivity();

  auto finish = [&](std::vector<std::uint8_t> resp) {
    const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                        std::chrono::steady_clock::now() - t0)
                        .count();
    const auto budget = (session_ == UdsSession::kDefault) ? cfg_.p2_server_ms
                                                           : cfg_.p2_star_server_ms;
    if (budget > 0 && ms > static_cast<std::chrono::milliseconds::rep>(budget)) {
      // Observe only: do not rewrite positive responses (Activate/transfer may exceed P2*).
      std::cerr << "diag: P2* observe exceed sid=0x" << std::hex
                << static_cast<unsigned>(request[0]) << std::dec << " took=" << ms
                << "ms budget=" << budget << "ms (response kept)\n";
    }
    return resp;
  };

  if (mcu_ && !request.empty() && request[0] == 0xFE && request.size() > 1) {
    std::vector<std::uint8_t> inner(request.begin() + 1, request.end());
    std::vector<std::uint8_t> resp;
    if (mcu_(inner, resp) && !resp.empty()) {
      return finish(std::move(resp));
    }
    return finish(MakeNrc(inner[0], UdsNrc::kGeneralReject));
  }

  const auto sid = request[0];
  switch (sid) {
    case 0x10: {
      if (request.size() < 2) {
        return finish(MakeNrc(0x10, UdsNrc::kIncorrectMessageLength));
      }
      const auto sf = static_cast<UdsSession>(request[1] & 0x7F);
      if (sf != UdsSession::kDefault && sf != UdsSession::kProgramming &&
          sf != UdsSession::kExtended) {
        return finish(MakeNrc(0x10, UdsNrc::kSubFunctionNotSupported));
      }
      session_ = sf;
      if (sf == UdsSession::kDefault) {
        security_unlocked_ = false;
        AbortTransfer();
      }
      if (request[1] & 0x80) {
        return finish({});
      }
      return finish({0x50, request[1]});
    }
    case 0x11: {
      if (request.size() < 2) {
        return finish(MakeNrc(0x11, UdsNrc::kIncorrectMessageLength));
      }
      return finish({0x51, request[1]});
    }
    case 0x14: {
      // ClearDiagnosticInformation: 0x14 + 3-byte group (0xFFFFFF = all)
      if (request.size() < 4) {
        return finish(MakeNrc(0x14, UdsNrc::kIncorrectMessageLength));
      }
      const std::uint32_t group = (static_cast<std::uint32_t>(request[1]) << 16) |
                                  (static_cast<std::uint32_t>(request[2]) << 8) | request[3];
      (void)gf_ara::collector::EventCollector::Instance().ClearDtc(group);
      return finish({0x54});
    }
    case 0x19: {
      if (request.size() < 2) {
        return finish(MakeNrc(0x19, UdsNrc::kIncorrectMessageLength));
      }
      auto& col = gf_ara::collector::EventCollector::Instance();
      // SIL: apps persist DTC under shared GF_PER_DIR; reload so DoIP sees them.
      col.ReloadDtcsFromPer();
      const auto sf = static_cast<std::uint8_t>(request[1] & 0x7F);
      if (sf == 0x01) {
        if (request.size() < 3) {
          return finish(MakeNrc(0x19, UdsNrc::kIncorrectMessageLength));
        }
        const auto mask = request[2];
        const auto n = col.CountDtcs(mask);
        return finish({0x59, 0x01, 0xFF, 0x00, static_cast<std::uint8_t>((n >> 8) & 0xFF),
                       static_cast<std::uint8_t>(n & 0xFF)});
      }
      if (sf == 0x02) {
        if (request.size() < 3) {
          return finish(MakeNrc(0x19, UdsNrc::kIncorrectMessageLength));
        }
        const auto mask = request[2];
        std::vector<std::uint8_t> body = {0x59, 0x02, mask};
        for (const auto& d : col.ListDtcs(mask)) {
          body.push_back(static_cast<std::uint8_t>((d.code >> 16) & 0xFF));
          body.push_back(static_cast<std::uint8_t>((d.code >> 8) & 0xFF));
          body.push_back(static_cast<std::uint8_t>(d.code & 0xFF));
          body.push_back(d.status);
        }
        return finish(std::move(body));
      }
      if (sf == 0x04) {
        // lite: report freeze frame for DTC (req: 0x19 0x04 dtc[3] record#)
        if (request.size() < 6) {
          return finish(MakeNrc(0x19, UdsNrc::kIncorrectMessageLength));
        }
        const std::uint32_t dtc = (static_cast<std::uint32_t>(request[2]) << 16) |
                                  (static_cast<std::uint32_t>(request[3]) << 8) | request[4];
        std::string blob;
        std::uint64_t t_ns = 0;
        if (!col.GetFreezeFrame(dtc, blob, t_ns)) {
          return finish(MakeNrc(0x19, UdsNrc::kRequestOutOfRange));
        }
        std::vector<std::uint8_t> body = {0x59, 0x04, request[2], request[3], request[4],
                                          request[5]};
        body.push_back(static_cast<std::uint8_t>((t_ns >> 56) & 0xFF));
        body.push_back(static_cast<std::uint8_t>((t_ns >> 48) & 0xFF));
        body.push_back(static_cast<std::uint8_t>((t_ns >> 40) & 0xFF));
        body.push_back(static_cast<std::uint8_t>((t_ns >> 32) & 0xFF));
        body.insert(body.end(), blob.begin(), blob.end());
        return finish(std::move(body));
      }
      return finish(MakeNrc(0x19, UdsNrc::kSubFunctionNotSupported));
    }
    case 0x85: {
      if (request.size() < 2) {
        return finish(MakeNrc(0x85, UdsNrc::kIncorrectMessageLength));
      }
      const auto sf = static_cast<std::uint8_t>(request[1] & 0x7F);
      if (sf == 0x01) {
        gf_ara::collector::EventCollector::Instance().SetDtcControlEnabled(true);
      } else if (sf == 0x02) {
        gf_ara::collector::EventCollector::Instance().SetDtcControlEnabled(false);
      } else {
        return finish(MakeNrc(0x85, UdsNrc::kSubFunctionNotSupported));
      }
      if (request[1] & 0x80) {
        return finish({});
      }
      return finish({0xC5, request[1]});
    }
    case 0x22: {
      if (request.size() < 3) {
        return finish(MakeNrc(0x22, UdsNrc::kIncorrectMessageLength));
      }
      const auto did = Be16(request.data() + 1);
      const auto it = dids_.find(did);
      if (it == dids_.end()) {
        return finish(MakeNrc(0x22, UdsNrc::kRequestOutOfRange));
      }
      std::vector<std::uint8_t> body = {0x62, request[1], request[2]};
      body.insert(body.end(), it->second.begin(), it->second.end());
      return finish(std::move(body));
    }
    case 0x2E: {
      if (request.size() < 3) {
        return finish(MakeNrc(0x2E, UdsNrc::kIncorrectMessageLength));
      }
      if (!security_unlocked_ && session_ != UdsSession::kExtended &&
          session_ != UdsSession::kProgramming) {
        return finish(MakeNrc(0x2E, UdsNrc::kSecurityAccessDenied));
      }
      const auto did = Be16(request.data() + 1);
      const std::vector<std::uint8_t> payload(request.begin() + 3, request.end());
      if (payload.size() > did_max_payload_) {
        return finish(MakeNrc(0x2E, UdsNrc::kIncorrectMessageLength));
      }
      if (dids_.find(did) == dids_.end() && dids_.size() >= did_max_entries_) {
        return finish(MakeNrc(0x2E, UdsNrc::kGeneralReject));
      }
      dids_[did] = payload;
      return finish({0x6E, request[1], request[2]});
    }
    case 0x27:
      return finish(HandleSecurityAccess(request));
    case 0x29:
      return finish(HandleAuthentication(request));
    case 0x31: {
      if (request.size() < 4) {
        return finish(MakeNrc(0x31, UdsNrc::kIncorrectMessageLength));
      }
      // RID F201: dump EventCollector ring as NDJSON (GMT remote read over DoIP).
      // req: 0x31 0x01 0xF2 0x01 [offset_be16] [max_be16]
      // resp: 0x71 0x01 0xF2 0x01 total_be16 offset_be16 count_be16 + utf8 NDJSON
      if (request[1] == 0x01 && request[2] == 0xF2 && request[3] == 0x01) {
        std::uint16_t offset = 0;
        std::uint16_t max_n = 200;
        if (request.size() >= 6) {
          offset = Be16(request.data() + 4);
        }
        if (request.size() >= 8) {
          max_n = Be16(request.data() + 6);
        }
        if (max_n == 0) {
          max_n = 200;
        }
        if (max_n > 500) {
          max_n = 500;
        }
        const auto snap = gf_ara::collector::EventCollector::Instance().Snapshot();
        const auto total = static_cast<std::uint16_t>(
            snap.size() > 0xFFFF ? 0xFFFF : snap.size());
        if (offset > total) {
          offset = total;
        }
        std::ostringstream nd;
        std::uint16_t count = 0;
        for (std::size_t i = offset; i < snap.size() && count < max_n; ++i) {
          const auto& e = snap[i];
          auto esc = [](std::string s) {
            for (char& c : s) {
              if (c == '"' || c == '\\' || c == '\n' || c == '\r') {
                c = '_';
              }
            }
            return s;
          };
          nd << "{\"t_ns\":" << e.t_ns << ",\"source\":\"" << esc(e.source)
             << "\",\"id\":\"" << esc(e.event_id) << "\",\"detail\":\""
             << esc(e.detail) << "\",\"pid\":0}\n";
          ++count;
          if (nd.tellp() > 48000) {
            break;
          }
        }
        const std::string body_s = nd.str();
        std::vector<std::uint8_t> body = {0x71, 0x01, 0xF2, 0x01};
        body.push_back(static_cast<std::uint8_t>((total >> 8) & 0xFF));
        body.push_back(static_cast<std::uint8_t>(total & 0xFF));
        body.push_back(static_cast<std::uint8_t>((offset >> 8) & 0xFF));
        body.push_back(static_cast<std::uint8_t>(offset & 0xFF));
        body.push_back(static_cast<std::uint8_t>((count >> 8) & 0xFF));
        body.push_back(static_cast<std::uint8_t>(count & 0xFF));
        body.insert(body.end(), body_s.begin(), body_s.end());
        return finish(std::move(body));
      }
      if (routine_) {
        return finish(routine_(request));
      }
      return finish(MakeNrc(0x31, UdsNrc::kRequestOutOfRange));
    }
    case 0x34:
      return finish(HandleRequestDownload(request));
    case 0x36:
      return finish(HandleTransferData(request));
    case 0x37:
      return finish(HandleRequestTransferExit(request));
    case 0x38:
      return finish(HandleRequestFileTransfer(request));
    case 0x3E: {
      if (request.size() < 2) {
        return finish(MakeNrc(0x3E, UdsNrc::kIncorrectMessageLength));
      }
      if (request[1] & 0x80) {
        return finish({});
      }
      return finish({0x7E, request[1]});
    }
    default:
      return finish(MakeNrc(sid, UdsNrc::kServiceNotSupported));
  }
}

}  // namespace gf_ara::diag
