#pragma once

#include <cstdint>
#include <optional>
#include <string>

#include "gf_ara/com/binding/iceoryx/event.hpp"
#include "gf_ara/com/service_path.hpp"
#include "iceoryx_posh/popo/subscriber.hpp"

namespace gf_gen {

struct SurroundObject {
  uint8_t object_id;
  uint8_t object_class;
  float long_dist_m;
  float lat_dist_m;
  float rel_vel_long_mps;
  float length_m;
  float width_m;
  float heading_rad;
};

struct DetectedParkingSlot {
  uint8_t slot_id;
  float center_x_m;
  float center_y_m;
  float yaw_rad;
  float length_m;
  float width_m;
  uint8_t free;
  uint8_t slot_type;
};

struct SurroundWorld {
  uint64_t timestamp_ns;
  uint8_t n_obj;
  SurroundObject objects[16];
  uint8_t n_slot;
  DetectedParkingSlot slots[6];
};

class SurroundWorldSkeleton {
 public:
  static constexpr const char* kService = "semantic.SurroundWorld";
  static constexpr const char* kEvent = "SurroundWorld";

  explicit SurroundWorldSkeleton(std::string instance = "1")
      : pub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}

  gf_ara::core::Result<void> Send(const SurroundWorld& sample) {
    return pub_.Publish(sample);
  }

 private:
  gf_ara::com::binding::iceoryx::EventPublisher<SurroundWorld> pub_;
};

class SurroundWorldProxy {
 public:
  static constexpr const char* kService = "semantic.SurroundWorld";
  static constexpr const char* kEvent = "SurroundWorld";

  explicit SurroundWorldProxy(std::string instance = "1")
      : sub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}

  gf_ara::core::Result<std::optional<SurroundWorld>> Take() {
    return sub_.Take();
  }

  [[nodiscard]] bool HasData() const noexcept { return sub_.HasData(); }

  [[nodiscard]] iox::popo::Subscriber<SurroundWorld>& Native() noexcept {
    return sub_.Native();
  }
  [[nodiscard]] const iox::popo::Subscriber<SurroundWorld>& Native() const noexcept {
    return sub_.Native();
  }

 private:
  gf_ara::com::binding::iceoryx::EventSubscriber<SurroundWorld> sub_;
};

}  // namespace gf_gen
