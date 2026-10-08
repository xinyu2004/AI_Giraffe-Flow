#pragma once

#include <cstdint>
#include <optional>
#include <string>

#include "gf_ara/com/binding/iceoryx/event.hpp"
#include "gf_ara/com/service_path.hpp"
#include "iceoryx_posh/popo/subscriber.hpp"

namespace gf_gen {

struct FreespaceNear {
  uint64_t timestamp_ns;
  float d_r_m[180];
  uint8_t type[180];
  uint8_t valid;
};

class FreespaceNearSkeleton {
 public:
  static constexpr const char* kService = "semantic.FreespaceNear";
  static constexpr const char* kEvent = "FreespaceNear";

  explicit FreespaceNearSkeleton(std::string instance = "1")
      : pub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}

  gf_ara::core::Result<void> Send(const FreespaceNear& sample) {
    return pub_.Publish(sample);
  }

 private:
  gf_ara::com::binding::iceoryx::EventPublisher<FreespaceNear> pub_;
};

class FreespaceNearProxy {
 public:
  static constexpr const char* kService = "semantic.FreespaceNear";
  static constexpr const char* kEvent = "FreespaceNear";

  explicit FreespaceNearProxy(std::string instance = "1")
      : sub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}

  gf_ara::core::Result<std::optional<FreespaceNear>> Take() {
    return sub_.Take();
  }

  [[nodiscard]] bool HasData() const noexcept { return sub_.HasData(); }

  [[nodiscard]] iox::popo::Subscriber<FreespaceNear>& Native() noexcept {
    return sub_.Native();
  }
  [[nodiscard]] const iox::popo::Subscriber<FreespaceNear>& Native() const noexcept {
    return sub_.Native();
  }

 private:
  gf_ara::com::binding::iceoryx::EventSubscriber<FreespaceNear> sub_;
};

}  // namespace gf_gen
