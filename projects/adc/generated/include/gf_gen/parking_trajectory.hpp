#pragma once

#include <cstdint>
#include <optional>
#include <string>

#include "gf_ara/com/binding/iceoryx/event.hpp"
#include "gf_ara/com/service_path.hpp"
#include "iceoryx_posh/popo/subscriber.hpp"

namespace gf_gen {

struct ParkingTrajectory {
  uint64_t timestamp_ns;
  uint8_t valid;
  uint8_t n_points;
  float x_m[32];
  float y_m[32];
  float yaw_rad[32];
};

class ParkingTrajectorySkeleton {
 public:
  static constexpr const char* kService = "semantic.ParkingTrajectory";
  static constexpr const char* kEvent = "ParkingTrajectory";

  explicit ParkingTrajectorySkeleton(std::string instance = "1")
      : pub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}

  gf_ara::core::Result<void> Send(const ParkingTrajectory& sample) {
    return pub_.Publish(sample);
  }

 private:
  gf_ara::com::binding::iceoryx::EventPublisher<ParkingTrajectory> pub_;
};

class ParkingTrajectoryProxy {
 public:
  static constexpr const char* kService = "semantic.ParkingTrajectory";
  static constexpr const char* kEvent = "ParkingTrajectory";

  explicit ParkingTrajectoryProxy(std::string instance = "1")
      : sub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}

  gf_ara::core::Result<std::optional<ParkingTrajectory>> Take() {
    return sub_.Take();
  }

  [[nodiscard]] bool HasData() const noexcept { return sub_.HasData(); }

  [[nodiscard]] iox::popo::Subscriber<ParkingTrajectory>& Native() noexcept {
    return sub_.Native();
  }
  [[nodiscard]] const iox::popo::Subscriber<ParkingTrajectory>& Native() const noexcept {
    return sub_.Native();
  }

 private:
  gf_ara::com::binding::iceoryx::EventSubscriber<ParkingTrajectory> sub_;
};

}  // namespace gf_gen
