#pragma once

#include <cstdint>
#include <optional>
#include <string>

#include "gf_ara/com/binding/iceoryx/event.hpp"
#include "gf_ara/com/service_path.hpp"
#include "iceoryx_posh/popo/subscriber.hpp"

namespace gf_gen {

struct RcmLane {
  float c0_m;
  float c1_rad;
  float c2;
  float c3;
  float view_range_m;
  uint8_t quality;
  uint8_t side;
};

struct RcmObject {
  uint8_t object_id;
  uint8_t object_class;
  float long_dist_m;
  float lat_dist_m;
  float rel_vel_long_mps;
  float rel_vel_lat_mps;
  float abs_vel_mps;
};

struct Perception_Rear_Out_St {
  uint64_t timestamp_ns;
  uint8_t valid;
  uint8_t n_lane;
  RcmLane lanes[8];
  uint8_t n_obj;
  RcmObject objects[16];
};

class Perception_Rear_Out_StSkeleton {
 public:
  static constexpr const char* kService = "semantic.Perception_Rear_Out_St";
  static constexpr const char* kEvent = "Perception_Rear_Out_St";

  explicit Perception_Rear_Out_StSkeleton(std::string instance = "1")
      : pub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}

  gf_ara::core::Result<void> Send(const Perception_Rear_Out_St& sample) {
    return pub_.Publish(sample);
  }

 private:
  gf_ara::com::binding::iceoryx::EventPublisher<Perception_Rear_Out_St> pub_;
};

class Perception_Rear_Out_StProxy {
 public:
  static constexpr const char* kService = "semantic.Perception_Rear_Out_St";
  static constexpr const char* kEvent = "Perception_Rear_Out_St";

  explicit Perception_Rear_Out_StProxy(std::string instance = "1")
      : sub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}

  gf_ara::core::Result<std::optional<Perception_Rear_Out_St>> Take() {
    return sub_.Take();
  }

  [[nodiscard]] bool HasData() const noexcept { return sub_.HasData(); }

  [[nodiscard]] iox::popo::Subscriber<Perception_Rear_Out_St>& Native() noexcept {
    return sub_.Native();
  }
  [[nodiscard]] const iox::popo::Subscriber<Perception_Rear_Out_St>& Native() const noexcept {
    return sub_.Native();
  }

 private:
  gf_ara::com::binding::iceoryx::EventSubscriber<Perception_Rear_Out_St> sub_;
};

}  // namespace gf_gen
