#include "gf_ara/com/binding/dds/event.hpp"
#include "gf_ara/com/binding/dds/runtime.hpp"

#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <thread>

namespace {

struct Sample {
  std::uint32_t seq{0};
  float value{0.f};
};

}  // namespace

int main() {
  using gf_ara::com::ServicePath;
  using gf_ara::com::binding::dds::BackendName;
  using gf_ara::com::binding::dds::EventPublisher;
  using gf_ara::com::binding::dds::EventSubscriber;
  using gf_ara::com::binding::dds::InitRuntime;

  InitRuntime("gf-dds-smoke");
  const auto backend = BackendName();
  std::cout << "gf_dds_binding_smoke backend=" << backend << "\n";

#if defined(GF_DDS_USE_CYCLONEDDS) && GF_DDS_USE_CYCLONEDDS
  if (std::strcmp(backend.data(), "cyclonedds") != 0) {
    std::cerr << "gf_dds_binding_smoke FAIL: expected cyclonedds backend\n";
    return EXIT_FAILURE;
  }
#endif

  ServicePath path{"demo.Topic", "1", "Event"};
  // Subscriber first so discovery sees a reader before write
  EventSubscriber<Sample> sub{path};
  EventPublisher<Sample> pub{path};

  Sample s{};
  s.seq = 7;
  s.value = 3.14f;
  if (!pub.Publish(s)) {
    std::cerr << "gf_dds_binding_smoke FAIL: Publish\n";
    return EXIT_FAILURE;
  }

  bool ok = false;
  for (int i = 0; i < 50; ++i) {
    auto got = sub.Take();
    if (got && got.Value().has_value() && got.Value()->seq == 7) {
      ok = true;
      break;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
  }
  if (!ok) {
    std::cerr << "gf_dds_binding_smoke FAIL: Take (no sample within timeout)\n";
    return EXIT_FAILURE;
  }

  std::cout << "gf_dds_binding_smoke OK backend=" << backend << "\n";
  return EXIT_SUCCESS;
}
