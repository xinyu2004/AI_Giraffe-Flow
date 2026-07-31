#include "gf_ara/com/binding/someip/runtime.hpp"

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
  using namespace gf_ara::com::binding::someip;
  if (IsInitialized()) {
    return Fail("SIP-01", "premature init");
  }
  Pass("SIP-01", "not initialized before Init");

  InitRuntime("gf-someip-smoke");
  if (!IsInitialized() || BackendName().empty()) {
    return Fail("SIP-02", "Init");
  }
  Pass("SIP-02", "InitRuntime");

  Shutdown();
  if (IsInitialized()) {
    return Fail("SIP-03", "Shutdown");
  }
  Pass("SIP-03", "Shutdown");

  std::cout << "gf_someip_binding_smoke OK backend=stub\n";
  return EXIT_SUCCESS;
}
