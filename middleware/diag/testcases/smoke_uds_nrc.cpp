#include "gf_ara/diag/uds_dispatcher.hpp"
#include "gf_ara/diag/uds_nrc.hpp"

#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

namespace {

int Fail(const char* id, const char* msg) {
  std::cerr << "CASE " << id << " FAIL " << msg << '\n';
  return EXIT_FAILURE;
}

void Pass(const char* id, const char* detail) {
  std::cout << "CASE " << id << " PASS " << detail << '\n';
}

bool IsNrc(const std::vector<std::uint8_t>& r, std::uint8_t sid, std::uint8_t nrc) {
  return r.size() >= 3 && r[0] == 0x7F && r[1] == sid && r[2] == nrc;
}

}  // namespace

int main() {
  using gf_ara::diag::UdsDispatcher;
  using gf_ara::diag::UdsConfig;

  if (!UdsDispatcher::StandardsValid(true, true) ||
      UdsDispatcher::StandardsValid(false, true) ||
      !UdsDispatcher::StandardsValid(true, false)) {
    return Fail("UDS-00", "StandardsValid");
  }
  Pass("UDS-00", "13400 requires 14229");

  UdsConfig cfg;
  cfg.iso_14229_uds = true;
  cfg.iso_13400_doip = false;
  cfg.security_delay_ms = 0;  // default product delay covered below
  UdsDispatcher::Instance().Configure(cfg);

  auto& uds = UdsDispatcher::Instance();

  // 0x10 session
  auto s = uds.Handle({0x10, 0x03});
  if (s.size() < 2 || s[0] != 0x50) {
    return Fail("UDS-10", "extended session");
  }
  Pass("UDS-10", "DiagnosticSessionControl");

  auto bad_sf = uds.Handle({0x10, 0x7F});
  if (!IsNrc(bad_sf, 0x10, 0x12)) {
    return Fail("UDS-10N", "NRC subFunctionNotSupported");
  }
  Pass("UDS-10N", "NRC 0x12");

  // 0x3E
  auto tp = uds.Handle({0x3E, 0x00});
  if (tp.empty() || tp[0] != 0x7E) {
    return Fail("UDS-3E", "TesterPresent");
  }
  Pass("UDS-3E", "TesterPresent");

  // 0x22 missing DID → NRC 0x31
  auto miss = uds.Handle({0x22, 0xF1, 0x90});
  if (!IsNrc(miss, 0x22, 0x31)) {
    return Fail("UDS-22N", "NRC requestOutOfRange");
  }
  uds.SetDid(0xF190, {0x47, 0x46});
  auto rd = uds.Handle({0x22, 0xF1, 0x90});
  if (rd.size() < 5 || rd[0] != 0x62) {
    return Fail("UDS-22", "ReadDID");
  }
  Pass("UDS-22", "ReadDataByIdentifier + NRC");

  // 0x27 seed/key
  auto seed = uds.Handle({0x27, 0x01});
  if (seed.size() < 4 || seed[0] != 0x67) {
    return Fail("UDS-27a", "requestSeed");
  }
  auto badk = uds.Handle({0x27, 0x02, 0x00, 0x00});
  if (!IsNrc(badk, 0x27, 0x35)) {
    return Fail("UDS-27N", "NRC invalidKey");
  }
  seed = uds.Handle({0x27, 0x01});
  auto okk = uds.Handle({0x27, 0x02, 0x55, 0xAA});
  if (okk.size() < 2 || okk[0] != 0x67 || !uds.SecurityUnlocked()) {
    return Fail("UDS-27b", "sendKey");
  }
  Pass("UDS-27", "SecurityAccess + NRC");

  // 0x27 requiredTimeDelayNotExpired after bad key
  {
    UdsConfig dcfg = cfg;
    dcfg.security_delay_ms = 200;
    uds.Configure(dcfg);
    (void)uds.Handle({0x27, 0x01});
    (void)uds.Handle({0x27, 0x02, 0x00, 0x00});
    auto dly = uds.Handle({0x27, 0x01});
    if (!IsNrc(dly, 0x27, 0x37)) {
      return Fail("UDS-27D", "NRC RequiredTimeDelayNotExpired");
    }
    Pass("UDS-27D", "security_delay_ms → NRC 0x37");
    uds.Configure(cfg);
    uds.SetDid(0xF190, {0x01, 0x02, 0x03});
    // re-unlock for later 0x2E
    (void)uds.Handle({0x10, 0x03});
    (void)uds.Handle({0x27, 0x01});
    (void)uds.Handle({0x27, 0x02, 0x55, 0xAA});
  }

  // 0x29
  auto a = uds.Handle({0x29, 0x00});
  if (a.size() < 2 || a[0] != 0x69) {
    return Fail("UDS-29", "Authentication stub");
  }
  Pass("UDS-29", "Authentication");

  // 0x2E after unlock
  auto wr = uds.Handle({0x2E, 0xF1, 0x91, 0x01});
  if (wr.size() < 3 || wr[0] != 0x6E) {
    return Fail("UDS-2E", "WriteDID");
  }
  Pass("UDS-2E", "WriteDataByIdentifier");

  // unknown SID
  auto uns = uds.Handle({0x99});
  if (!IsNrc(uns, 0x99, 0x11)) {
    return Fail("UDS-NS", "serviceNotSupported");
  }
  Pass("UDS-NS", "NRC 0x11");

  // MCU handoff: 0xFE + inner
  uds.SetMcuHandoff([](const std::vector<std::uint8_t>& req,
                       std::vector<std::uint8_t>& resp) {
    if (req.size() >= 1 && req[0] == 0x3E) {
      resp = {0x7E, 0x00};
      return true;
    }
    return false;
  });
  auto mcu = uds.Handle({0xFE, 0x3E, 0x00});
  if (mcu.empty() || mcu[0] != 0x7E) {
    return Fail("UDS-MCU", "PDU handoff");
  }
  Pass("UDS-MCU", "gateway PDU to MCU (no ISO-TP on AP)");

  std::cout << "gf_uds_nrc_smoke OK\n";
  return EXIT_SUCCESS;
}
