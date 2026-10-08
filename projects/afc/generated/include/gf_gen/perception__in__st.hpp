#pragma once

#include <cstdint>
#include <optional>
#include <string>

#include "gf_ara/com/binding/iceoryx/event.hpp"
#include "gf_ara/com/service_path.hpp"
#include "iceoryx_posh/popo/subscriber.hpp"

namespace gf_gen {

struct Perception_In_St {
  uint64_t timestamp_ns;
  uint32_t ipc_frame_counter;
  uint8_t gear;
  float vehicle_speed;
  float yaw_rate;
  uint8_t _vendor_payload_opaque[1];
};

class Perception_In_StSkeleton {
 public:
  static constexpr const char* kService = "semantic.Perception_In_St";
  static constexpr const char* kEvent = "Perception_In_St";

  explicit Perception_In_StSkeleton(std::string instance = "1")
      : pub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}

  gf_ara::core::Result<void> Send(const Perception_In_St& sample) {
    return pub_.Publish(sample);
  }

 private:
  gf_ara::com::binding::iceoryx::EventPublisher<Perception_In_St> pub_;
};

class Perception_In_StProxy {
 public:
  static constexpr const char* kService = "semantic.Perception_In_St";
  static constexpr const char* kEvent = "Perception_In_St";

  explicit Perception_In_StProxy(std::string instance = "1")
      : sub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}

  gf_ara::core::Result<std::optional<Perception_In_St>> Take() {
    return sub_.Take();
  }

  [[nodiscard]] bool HasData() const noexcept { return sub_.HasData(); }

  [[nodiscard]] iox::popo::Subscriber<Perception_In_St>& Native() noexcept {
    return sub_.Native();
  }
  [[nodiscard]] const iox::popo::Subscriber<Perception_In_St>& Native() const noexcept {
    return sub_.Native();
  }

 private:
  gf_ara::com::binding::iceoryx::EventSubscriber<Perception_In_St> sub_;
};

}  // namespace gf_gen
