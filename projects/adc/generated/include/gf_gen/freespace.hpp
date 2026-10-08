#pragma once

#include <cstdint>
#include <optional>
#include <string>

#include "gf_ara/com/binding/iceoryx/event.hpp"
#include "gf_ara/com/service_path.hpp"
#include "iceoryx_posh/popo/subscriber.hpp"

namespace gf_gen {

struct Freespace {
  uint64_t timestamp_ns;
  float d_lane_fwd_m[3];
  uint8_t n_poly;
  float poly_x_m[180];
  float poly_y_m[180];
  uint8_t valid;
};

class FreespaceSkeleton {
 public:
  static constexpr const char* kService = "semantic.Freespace";
  static constexpr const char* kEvent = "Freespace";

  explicit FreespaceSkeleton(std::string instance = "1")
      : pub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}

  gf_ara::core::Result<void> Send(const Freespace& sample) {
    return pub_.Publish(sample);
  }

 private:
  gf_ara::com::binding::iceoryx::EventPublisher<Freespace> pub_;
};

class FreespaceProxy {
 public:
  static constexpr const char* kService = "semantic.Freespace";
  static constexpr const char* kEvent = "Freespace";

  explicit FreespaceProxy(std::string instance = "1")
      : sub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}

  gf_ara::core::Result<std::optional<Freespace>> Take() {
    return sub_.Take();
  }

  [[nodiscard]] bool HasData() const noexcept { return sub_.HasData(); }

  [[nodiscard]] iox::popo::Subscriber<Freespace>& Native() noexcept {
    return sub_.Native();
  }
  [[nodiscard]] const iox::popo::Subscriber<Freespace>& Native() const noexcept {
    return sub_.Native();
  }

 private:
  gf_ara::com::binding::iceoryx::EventSubscriber<Freespace> sub_;
};

}  // namespace gf_gen
