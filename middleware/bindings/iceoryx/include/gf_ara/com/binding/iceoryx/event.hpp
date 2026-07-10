#ifndef GF_ARA_COM_BINDING_ICEORYX_EVENT_HPP
#define GF_ARA_COM_BINDING_ICEORYX_EVENT_HPP

#include "gf_ara/com/service_path.hpp"
#include "gf_ara/core/result.hpp"

#include "iceoryx_hoofs/cxx/string.hpp"
#include "iceoryx_posh/capro/service_description.hpp"
#include "iceoryx_posh/popo/publisher.hpp"
#include "iceoryx_posh/popo/subscriber.hpp"

#include <optional>
#include <type_traits>

namespace gf_ara::com::binding::iceoryx {

using gf_ara::com::ServicePath;

inline iox::capro::ServiceDescription ToServiceDescription(const ServicePath& path) {
  using IdString_t = iox::capro::IdString_t;
  return iox::capro::ServiceDescription{
      IdString_t(iox::cxx::TruncateToCapacity, path.service.c_str()),
      IdString_t(iox::cxx::TruncateToCapacity, path.instance.c_str()),
      IdString_t(iox::cxx::TruncateToCapacity, path.event.c_str()),
  };
}

/// iceoryx-backed Event publisher (requires RouDi + InitRuntime).
template <typename T>
class EventPublisher {
 public:
  explicit EventPublisher(ServicePath path)
      : path_(std::move(path)), publisher_(ToServiceDescription(path_)) {
    static_assert(std::is_trivially_copyable_v<T>,
                  "P0 Event payload must be trivially copyable (POD)");
  }

  [[nodiscard]] const ServicePath& Path() const noexcept { return path_; }

  gf_ara::core::Result<void> Publish(const T& sample) {
    auto result = publisher_.publishCopyOf(sample);
    if (result.has_error()) {
      return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kBusy);
    }
    return gf_ara::core::Result<void>::Ok();
  }

 private:
  ServicePath path_;
  iox::popo::Publisher<T> publisher_;
};

/// iceoryx-backed Event subscriber (requires RouDi + InitRuntime).
template <typename T>
class EventSubscriber {
 public:
  explicit EventSubscriber(ServicePath path)
      : path_(std::move(path)), subscriber_(ToServiceDescription(path_)) {
    static_assert(std::is_trivially_copyable_v<T>,
                  "P0 Event payload must be trivially copyable (POD)");
  }

  [[nodiscard]] const ServicePath& Path() const noexcept { return path_; }

  gf_ara::core::Result<std::optional<T>> Take() {
    std::optional<T> out;
    auto err = gf_ara::core::ErrorCode::kOk;
    bool hard_error = false;

    subscriber_.take()
        .and_then([&](const auto& sample) { out = *sample; })
        .or_else([&](auto& result) {
          if (result != iox::popo::ChunkReceiveResult::NO_CHUNK_AVAILABLE) {
            hard_error = true;
            err = gf_ara::core::ErrorCode::kNotAvailable;
          }
        });

    if (hard_error) {
      return gf_ara::core::Result<std::optional<T>>::Err(err);
    }
    return gf_ara::core::Result<std::optional<T>>::Ok(out);
  }

 private:
  ServicePath path_;
  iox::popo::Subscriber<T> subscriber_;
};

}  // namespace gf_ara::com::binding::iceoryx

#endif
