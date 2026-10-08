#pragma once

#include <cstdint>
#include <optional>
#include <string>

#include "gf_ara/com/binding/iceoryx/event.hpp"
#include "gf_ara/com/service_path.hpp"
#include "iceoryx_posh/popo/subscriber.hpp"

namespace gf_gen {

struct ParkingSlot {
  uint64_t timestamp_ns;
  float fParkingSlot_P0X;
  float fParkingSlot_P0Y;
  float fParkingSlot_P1X;
  float fParkingSlot_P1Y;
  float fParkingSlot_P2X;
  float fParkingSlot_P2Y;
  uint8_t uiAPAOnOff;
  uint8_t uiAPAStatus;
};

class ParkingSlotSkeleton {
 public:
  static constexpr const char* kService = "semantic.ParkingSlot";
  static constexpr const char* kEvent = "ParkingSlot";

  explicit ParkingSlotSkeleton(std::string instance = "1")
      : pub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}

  gf_ara::core::Result<void> Send(const ParkingSlot& sample) {
    return pub_.Publish(sample);
  }

 private:
  gf_ara::com::binding::iceoryx::EventPublisher<ParkingSlot> pub_;
};

class ParkingSlotProxy {
 public:
  static constexpr const char* kService = "semantic.ParkingSlot";
  static constexpr const char* kEvent = "ParkingSlot";

  explicit ParkingSlotProxy(std::string instance = "1")
      : sub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}

  gf_ara::core::Result<std::optional<ParkingSlot>> Take() {
    return sub_.Take();
  }

  [[nodiscard]] bool HasData() const noexcept { return sub_.HasData(); }

  [[nodiscard]] iox::popo::Subscriber<ParkingSlot>& Native() noexcept {
    return sub_.Native();
  }
  [[nodiscard]] const iox::popo::Subscriber<ParkingSlot>& Native() const noexcept {
    return sub_.Native();
  }

 private:
  gf_ara::com::binding::iceoryx::EventSubscriber<ParkingSlot> sub_;
};

}  // namespace gf_gen
