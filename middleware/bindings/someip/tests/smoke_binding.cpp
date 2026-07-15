#include "gf_ara/com/binding/someip/runtime.hpp"

#include <cstdlib>
#include <iostream>

int main() {
  using namespace gf_ara::com::binding::someip;
  if (IsInitialized()) {
    std::cerr << "gf_someip_binding_smoke FAIL: premature init\n";
    return EXIT_FAILURE;
  }
  InitRuntime("gf-someip-smoke");
  if (!IsInitialized() || BackendName().empty()) {
    std::cerr << "gf_someip_binding_smoke FAIL: Init\n";
    return EXIT_FAILURE;
  }
  Shutdown();
  if (IsInitialized()) {
    std::cerr << "gf_someip_binding_smoke FAIL: Shutdown\n";
    return EXIT_FAILURE;
  }
  std::cout << "gf_someip_binding_smoke OK backend=stub\n";
  return EXIT_SUCCESS;
}
