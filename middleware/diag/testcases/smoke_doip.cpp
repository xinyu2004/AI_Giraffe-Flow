#include "gf_ara/diag/doip.hpp"

#include <cstdlib>
#include <iostream>

namespace {

int Fail(const char* id, const char* msg) {
  std::cerr << "CASE " << id << " FAIL " << msg << '\n';
  return EXIT_FAILURE;
}

void Pass(const char* id, const char* detail) {
  std::cout << "CASE " << id << " PASS " << detail << '\n';
}

}  // namespace

int main() {
  using gf_ara::diag::DoipConfig;
  using gf_ara::diag::DoipStack;
  using gf_ara::diag::RoutingActivationResponse;

  if (DoipStack::Shutdown()) {
    return Fail("DIAG-01", "Shutdown before Init");
  }
  Pass("DIAG-01", "Shutdown before Init rejected");

  DoipConfig cfg;
  cfg.logical_address = "GF-ECU-01";
  cfg.source_address = 0x0E00;
  cfg.target_address = 0x0001;

  if (!DoipStack::Initialize(cfg)) {
    return Fail("DIAG-02", "Initialize");
  }
  Pass("DIAG-02", "Initialize");

  auto act = DoipStack::RequestRoutingActivation(0x0001);
  if (!act || act.Value() != RoutingActivationResponse::kSuccess) {
    return Fail("DIAG-03", "RoutingActivation");
  }
  Pass("DIAG-03", "RoutingActivation success");

  if (!DoipStack::SendDiagnosticMessage(0x0001, {0x3E, 0x00})) {
    return Fail("DIAG-04", "SendDiagnosticMessage");
  }
  auto rx = DoipStack::ReceiveDiagnosticMessage();
  if (!rx || rx.Value().empty() || rx.Value()[0] != 0x7E) {
    return Fail("DIAG-04", "ReceiveDiagnosticMessage");
  }
  Pass("DIAG-04", "TesterPresent echo");

  if (!DoipStack::Shutdown()) {
    return Fail("DIAG-05", "Shutdown");
  }
  Pass("DIAG-05", "Shutdown");

  std::cout << "gf_diag_doip_smoke OK\n";
  return EXIT_SUCCESS;
}
