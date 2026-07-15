#include "gf_ara/com/binding/dds/event.hpp"
#include "gf_ara/com/binding/dds/runtime.hpp"

#include <cstdint>
#include <cstdlib>
#include <iostream>

namespace {

struct Sample {
  std::uint32_t seq{0};
  float value{0.f};
};

}  // namespace

int main() {
  using gf_ara::com::ServicePath;
  using gf_ara::com::binding::dds::EventPublisher;
  using gf_ara::com::binding::dds::EventSubscriber;
  using gf_ara::com::binding::dds::InitRuntime;
  using gf_ara::com::binding::dds::BackendName;

  InitRuntime("gf-dds-smoke");
  std::cout << "gf_dds_binding_smoke backend=" << BackendName() << "\n";

  ServicePath path{"demo.Topic", "1", "Event"};
  EventPublisher<Sample> pub{path};
  EventSubscriber<Sample> sub{path};

  Sample s{};
  s.seq = 7;
  s.value = 3.14f;
  if (!pub.Publish(s)) {
    std::cerr << "gf_dds_binding_smoke FAIL: Publish\n";
    return EXIT_FAILURE;
  }
  auto got = sub.Take();
  if (!got || !got.Value().has_value() || got.Value()->seq != 7) {
    std::cerr << "gf_dds_binding_smoke FAIL: Take\n";
    return EXIT_FAILURE;
  }

  std::cout << "gf_dds_binding_smoke OK\n";
  return EXIT_SUCCESS;
}
