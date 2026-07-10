#include "gf_ara/com/event.hpp"

#include <cstdlib>
#include <iostream>

namespace {

struct EgoMotionSample {
  float vx;
  float yaw_rate;
};

int Fail(const char* msg) {
  std::cerr << "gf_com_loopback_smoke FAIL: " << msg << '\n';
  return EXIT_FAILURE;
}

}  // namespace

int main() {
  using gf_ara::com::EventPublisher;
  using gf_ara::com::EventSubscriber;
  using gf_ara::com::LoopbackBus;
  using gf_ara::com::ServicePath;

  LoopbackBus::Instance().Clear();

  const ServicePath path{"semantic.vehicle_motion", "1", "EgoMotion"};
  EventPublisher<EgoMotionSample> pub{path};
  EventSubscriber<EgoMotionSample> sub{path};

  EgoMotionSample in{1.5f, 0.02f};
  if (!pub.Publish(in)) {
    return Fail("Publish");
  }

  auto taken = sub.Take();
  if (!taken || !taken.Value().has_value()) {
    return Fail("Take empty");
  }
  const auto out = *taken.Value();
  if (out.vx != in.vx || out.yaw_rate != in.yaw_rate) {
    return Fail("payload mismatch");
  }

  auto empty = sub.Take();
  if (!empty || empty.Value().has_value()) {
    return Fail("second Take should be empty");
  }

  std::cout << "gf_com_loopback_smoke OK\n";
  return EXIT_SUCCESS;
}
