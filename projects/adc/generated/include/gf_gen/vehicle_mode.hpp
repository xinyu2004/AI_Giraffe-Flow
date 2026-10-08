#pragma once

#include <cstdint>
#include <optional>
#include <string>

#include "gf_ara/com/binding/iceoryx/event.hpp"
#include "gf_ara/com/service_path.hpp"
#include "iceoryx_posh/popo/subscriber.hpp"

namespace gf_gen {

struct VehicleMode {
  uint64_t timestamp_ns;
  uint8_t mode;
  float speed_mps;
  uint8_t apa_armed;
};

class VehicleModeSkeleton {
 public:
  static constexpr const char* kService = "semantic.VehicleMode";
  static constexpr const char* kEvent = "VehicleMode";

  explicit VehicleModeSkeleton(std::string instance = "1")
      : pub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}

  gf_ara::core::Result<void> Send(const VehicleMode& sample) {
    return pub_.Publish(sample);
  }

 private:
  gf_ara::com::binding::iceoryx::EventPublisher<VehicleMode> pub_;
};

class VehicleModeProxy {
 public:
  static constexpr const char* kService = "semantic.VehicleMode";
  static constexpr const char* kEvent = "VehicleMode";

  explicit VehicleModeProxy(std::string instance = "1")
      : sub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}

  gf_ara::core::Result<std::optional<VehicleMode>> Take() {
    return sub_.Take();
  }

  [[nodiscard]] bool HasData() const noexcept { return sub_.HasData(); }

  [[nodiscard]] iox::popo::Subscriber<VehicleMode>& Native() noexcept {
    return sub_.Native();
  }
  [[nodiscard]] const iox::popo::Subscriber<VehicleMode>& Native() const noexcept {
    return sub_.Native();
  }

 private:
  gf_ara::com::binding::iceoryx::EventSubscriber<VehicleMode> sub_;
};

}  // namespace gf_gen
