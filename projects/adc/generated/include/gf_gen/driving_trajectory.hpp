#pragma once

#include <cstdint>
#include <optional>
#include <string>

#include "gf_ara/com/binding/iceoryx/event.hpp"
#include "gf_ara/com/service_path.hpp"
#include "iceoryx_posh/popo/subscriber.hpp"

namespace gf_gen {

struct DrivingTrajectory {
  uint64_t timestamp_ns;
  uint8_t point_count;
  float points_x_m[60];
  float points_y_m[60];
  float points_v_mps[60];
  uint8_t gear_shift_first;
  uint8_t gear_shift_second;
  float throttle;
  float brake;
  float steer;
  float target_speed_mps;
  uint8_t ctrl_mode;
  float D_see_m;
  float s_stop_m;
  float cipv_long_m;
  float cipv_rel_v;
  float v_sign_max_mps;
  float v_sign_min_mps;
};

class DrivingTrajectorySkeleton {
 public:
  static constexpr const char* kService = "semantic.DrivingTrajectory";
  static constexpr const char* kEvent = "DrivingTrajectory";

  explicit DrivingTrajectorySkeleton(std::string instance = "1")
      : pub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}

  gf_ara::core::Result<void> Send(const DrivingTrajectory& sample) {
    return pub_.Publish(sample);
  }

 private:
  gf_ara::com::binding::iceoryx::EventPublisher<DrivingTrajectory> pub_;
};

class DrivingTrajectoryProxy {
 public:
  static constexpr const char* kService = "semantic.DrivingTrajectory";
  static constexpr const char* kEvent = "DrivingTrajectory";

  explicit DrivingTrajectoryProxy(std::string instance = "1")
      : sub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}

  gf_ara::core::Result<std::optional<DrivingTrajectory>> Take() {
    return sub_.Take();
  }

  [[nodiscard]] bool HasData() const noexcept { return sub_.HasData(); }

  [[nodiscard]] iox::popo::Subscriber<DrivingTrajectory>& Native() noexcept {
    return sub_.Native();
  }
  [[nodiscard]] const iox::popo::Subscriber<DrivingTrajectory>& Native() const noexcept {
    return sub_.Native();
  }

 private:
  gf_ara::com::binding::iceoryx::EventSubscriber<DrivingTrajectory> sub_;
};

}  // namespace gf_gen
