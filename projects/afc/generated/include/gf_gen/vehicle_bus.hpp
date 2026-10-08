#pragma once

#include <cstdint>
#include <optional>
#include <string>

#include "gf_ara/com/binding/iceoryx/event.hpp"
#include "gf_ara/com/service_path.hpp"
#include "iceoryx_posh/popo/subscriber.hpp"

namespace gf_gen {

struct VehicleBus {
  uint64_t timestamp_ns;
  uint8_t _opaque[1];
};

class VehicleBusSkeleton {
 public:
  static constexpr const char* kService = "semantic.VehicleBus";
  static constexpr const char* kEvent = "VehicleBus";

  explicit VehicleBusSkeleton(std::string instance = "1")
      : pub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}

  gf_ara::core::Result<void> Send(const VehicleBus& sample) {
    return pub_.Publish(sample);
  }

 private:
  gf_ara::com::binding::iceoryx::EventPublisher<VehicleBus> pub_;
};

class VehicleBusProxy {
 public:
  static constexpr const char* kService = "semantic.VehicleBus";
  static constexpr const char* kEvent = "VehicleBus";

  explicit VehicleBusProxy(std::string instance = "1")
      : sub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}

  gf_ara::core::Result<std::optional<VehicleBus>> Take() {
    return sub_.Take();
  }

  [[nodiscard]] bool HasData() const noexcept { return sub_.HasData(); }

  [[nodiscard]] iox::popo::Subscriber<VehicleBus>& Native() noexcept {
    return sub_.Native();
  }
  [[nodiscard]] const iox::popo::Subscriber<VehicleBus>& Native() const noexcept {
    return sub_.Native();
  }

 private:
  gf_ara::com::binding::iceoryx::EventSubscriber<VehicleBus> sub_;
};

}  // namespace gf_gen
