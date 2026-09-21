#include "gf_ara/com/event.hpp"

#include <chrono>
#include <cstdlib>
#include <iostream>
#include <optional>
#include <thread>

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

  {
    EventPublisher<EgoMotionSample> pub2{path};
    EventSubscriber<EgoMotionSample> sub2{path};
    LoopbackBus::Instance().Clear();
    std::thread th([&] {
      std::this_thread::sleep_for(std::chrono::milliseconds(20));
      EgoMotionSample s{2.0f, 0.01f};
      (void)pub2.Publish(s);
    });
    auto w = sub2.Wait(std::optional<std::uint32_t>{200});
    th.join();
    if (!w) {
      return Fail("COM-04", "Wait timeout");
    }
    auto t2 = sub2.Take();
    if (!t2 || !t2.Value().has_value() || t2.Value()->vx != 2.0f) {
      return Fail("COM-04", "Wait/Take payload");
    }
    Pass("COM-04", "Wait wakes on Publish");
  }

  {
    LoopbackBus::Instance().Clear();
    EventSubscriber<EgoMotionSample> sub3{path};
    auto w = sub3.Wait(std::optional<std::uint32_t>{10});
    if (w) {
      return Fail("COM-05", "Wait should timeout");
    }
    Pass("COM-05", "Wait timeout");
  }

  std::cout << "gf_com_loopback_smoke OK\n";
  return EXIT_SUCCESS;
}
