#include "gf_ara/com/binding/iceoryx/status.hpp"

#include <cstdlib>
#include <cstring>
#include <iostream>

int main() {
  using gf_ara::com::binding::iceoryx::BackendLinked;
  using gf_ara::com::binding::iceoryx::BackendName;

  if (std::strcmp(BackendName(), "iceoryx") != 0) {
    std::cerr << "gf_iox_binding_smoke FAIL: BackendName\n";
    return EXIT_FAILURE;
  }
  if (!BackendLinked()) {
    std::cerr << "gf_iox_binding_smoke FAIL: BackendLinked\n";
    return EXIT_FAILURE;
  }
  std::cout << "gf_iox_binding_smoke OK (linked " << BackendName() << ")\n";
  return EXIT_SUCCESS;
}
