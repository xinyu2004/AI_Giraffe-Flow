#include "gf_ara/com/event.hpp"

#include <cstdlib>
#include <iostream>

namespace {

struct EgoMotionSample {
  float vx;
  float yaw_rate;
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
    return Fail("COM-01", "Publish");
  }
  Pass("COM-01", "Publish EgoMotion");

  auto taken = sub.Take();
  if (!taken || !taken.Value().has_value()) {
    return Fail("COM-02", "Take empty");
  }
  const auto out = *taken.Value();
  if (out.vx != in.vx || out.yaw_rate != in.yaw_rate) {
    return Fail("COM-02", "payload mismatch");
  }
  Pass("COM-02", "Take matches Publish");

  auto empty = sub.Take();
  if (!empty || empty.Value().has_value()) {
    return Fail("COM-03", "second Take should be empty");
  }
  Pass("COM-03", "second Take empty");

  std::cout << "gf_com_loopback_smoke OK\n";
  return EXIT_SUCCESS;
}
