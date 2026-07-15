#include "gf_ara/diag/doip.hpp"

#include <cstdlib>
#include <iostream>

int main() {
  using gf_ara::diag::DoipConfig;
  using gf_ara::diag::DoipStack;
  using gf_ara::diag::RoutingActivationResponse;

  if (DoipStack::Shutdown()) {
    std::cerr << "gf_diag_doip_smoke FAIL: Shutdown before Init\n";
    return EXIT_FAILURE;
  }

  DoipConfig cfg;
  cfg.logical_address = "GF-ECU-01";
  cfg.source_address = 0x0E00;
  cfg.target_address = 0x0001;

  if (!DoipStack::Initialize(cfg)) {
    std::cerr << "gf_diag_doip_smoke FAIL: Initialize\n";
    return EXIT_FAILURE;
  }

  auto act = DoipStack::RequestRoutingActivation(0x0001);
  if (!act || act.Value() != RoutingActivationResponse::kSuccess) {
    std::cerr << "gf_diag_doip_smoke FAIL: RoutingActivation\n";
    return EXIT_FAILURE;
  }

  // 诊断探针：TesterPresent
  if (!DoipStack::SendDiagnosticMessage(0x0001, {0x3E, 0x00})) {
    std::cerr << "gf_diag_doip_smoke FAIL: SendDiagnosticMessage\n";
    return EXIT_FAILURE;
  }
  auto rx = DoipStack::ReceiveDiagnosticMessage();
  if (!rx || rx.Value().empty() || rx.Value()[0] != 0x7E) {
    std::cerr << "gf_diag_doip_smoke FAIL: ReceiveDiagnosticMessage\n";
    return EXIT_FAILURE;
  }

  if (!DoipStack::Shutdown()) {
    std::cerr << "gf_diag_doip_smoke FAIL: Shutdown\n";
    return EXIT_FAILURE;
  }

  std::cout << "gf_diag_doip_smoke OK\n";
  return EXIT_SUCCESS;
}
