#pragma once

#include <cstdint>
#include <optional>
#include <string>

#include "gf_ara/com/binding/iceoryx/event.hpp"
#include "gf_ara/com/service_path.hpp"
#include "iceoryx_posh/popo/subscriber.hpp"

namespace gf_gen {

struct ApaStatus {
  uint64_t timestamp_ns;
  uint8_t uiAPAOnOff;
  uint8_t uiAPAStatus;
};

class ApaStatusSkeleton {
 public:
  static constexpr const char* kService = "semantic.ApaStatus";
  static constexpr const char* kEvent = "ApaStatus";

  explicit ApaStatusSkeleton(std::string instance = "1")
      : pub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}

  gf_ara::core::Result<void> Send(const ApaStatus& sample) {
    return pub_.Publish(sample);
  }

 private:
  gf_ara::com::binding::iceoryx::EventPublisher<ApaStatus> pub_;
};

class ApaStatusProxy {
 public:
  static constexpr const char* kService = "semantic.ApaStatus";
  static constexpr const char* kEvent = "ApaStatus";

  explicit ApaStatusProxy(std::string instance = "1")
      : sub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}

  gf_ara::core::Result<std::optional<ApaStatus>> Take() {
    return sub_.Take();
  }

  [[nodiscard]] bool HasData() const noexcept { return sub_.HasData(); }

  [[nodiscard]] iox::popo::Subscriber<ApaStatus>& Native() noexcept {
    return sub_.Native();
  }
  [[nodiscard]] const iox::popo::Subscriber<ApaStatus>& Native() const noexcept {
    return sub_.Native();
  }

 private:
  gf_ara::com::binding::iceoryx::EventSubscriber<ApaStatus> sub_;
};

}  // namespace gf_gen
