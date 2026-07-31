#include "gf_ara/com/binding/iceoryx/status.hpp"

#include <cstdlib>
#include <cstring>
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
  using gf_ara::com::binding::iceoryx::BackendLinked;
  using gf_ara::com::binding::iceoryx::BackendName;

  if (std::strcmp(BackendName(), "iceoryx") != 0) {
    return Fail("IOX-01", "BackendName");
  }
  Pass("IOX-01", "BackendName=iceoryx");

  if (!BackendLinked()) {
    return Fail("IOX-02", "BackendLinked");
  }
  Pass("IOX-02", "BackendLinked");

  std::cout << "gf_iox_binding_smoke OK (linked " << BackendName() << ")\n";
  return EXIT_SUCCESS;
}
