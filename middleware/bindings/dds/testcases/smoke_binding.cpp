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

int Fail(const char* id, const char* msg) {
  std::cerr << "CASE " << id << " FAIL " << msg << '\n';
  return EXIT_FAILURE;
}

void Pass(const char* id, const char* detail) {
  std::cout << "CASE " << id << " PASS " << detail << '\n';
}

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
  Pass("DDS-01", "InitRuntime");

#if defined(GF_DDS_USE_CYCLONEDDS) && GF_DDS_USE_CYCLONEDDS
  if (std::strcmp(backend.data(), "cyclonedds") != 0) {
    return Fail("DDS-02", "expected cyclonedds backend");
  }
  Pass("DDS-02", "backend=cyclonedds");
#else
  Pass("DDS-02", "backend stub or other");
#endif

  ServicePath path{"demo.Topic", "1", "Event"};
  EventSubscriber<Sample> sub{path};
  EventPublisher<Sample> pub{path};

  Sample s{};
  s.seq = 7;
  s.value = 3.14f;
  if (!pub.Publish(s)) {
    return Fail("DDS-03", "Publish");
  }
  Pass("DDS-03", "Publish");

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
    return Fail("DDS-04", "Take (no sample within timeout)");
  }
  Pass("DDS-04", "Take seq=7");

  std::cout << "gf_dds_binding_smoke OK backend=" << backend << "\n";
  return EXIT_SUCCESS;
}
