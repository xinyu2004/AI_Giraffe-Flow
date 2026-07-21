#pragma once

#include "gf_ara/com/binding/dds/runtime.hpp"
#include "gf_ara/com/service_path.hpp"
#include "gf_ara/core/result.hpp"

#include <cstdint>
#include <cstring>
#include <deque>
#include <mutex>
#include <optional>
#include <string>
#include <type_traits>
#include <unordered_map>
#include <vector>

#if defined(GF_DDS_USE_CYCLONEDDS) && GF_DDS_USE_CYCLONEDDS
#include "gf_ara/com/binding/dds/cyclone_transport.hpp"
#endif

namespace gf_ara::com::binding::dds {
namespace detail {

/// Process-local topic bus (offline stub / CI without CycloneDDS).
class TopicBus {
 public:
  static TopicBus& Instance() {
    static TopicBus bus;
    return bus;
  }

  void Publish(const std::string& key, const void* data, std::size_t size) {
    std::lock_guard<std::mutex> lock(mu_);
    auto& q = queues_[key];
    q.emplace_back(static_cast<const std::uint8_t*>(data),
                   static_cast<const std::uint8_t*>(data) + size);
    while (q.size() > 16) {
      q.pop_front();
    }
  }

  bool Take(const std::string& key, void* out, std::size_t size) {
    std::lock_guard<std::mutex> lock(mu_);
    auto it = queues_.find(key);
    if (it == queues_.end() || it->second.empty()) {
      return false;
    }
    const auto& bytes = it->second.front();
    if (bytes.size() != size) {
      it->second.pop_front();
      return false;
    }
    std::memcpy(out, bytes.data(), size);
    it->second.pop_front();
    return true;
  }

 private:
  std::mutex mu_;
  std::unordered_map<std::string, std::deque<std::vector<std::uint8_t>>> queues_;
};

}  // namespace detail

using gf_ara::com::ServicePath;

template <typename T>
class EventPublisher {
 public:
  explicit EventPublisher(ServicePath path) : path_(std::move(path)) {
    static_assert(std::is_trivially_copyable_v<T>,
                  "DDS Event payload must be trivially copyable (POD)");
#if defined(GF_DDS_USE_CYCLONEDDS) && GF_DDS_USE_CYCLONEDDS
    if (IsInitialized()) {
      cyclone_ = CycloneWriter(path_);
    }
#endif
  }

  [[nodiscard]] const ServicePath& Path() const noexcept { return path_; }

  gf_ara::core::Result<void> Publish(const T& sample) {
    if (!IsInitialized()) {
      return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
    }
#if defined(GF_DDS_USE_CYCLONEDDS) && GF_DDS_USE_CYCLONEDDS
    if (cyclone_.Ok()) {
      if (!cyclone_.Write(&sample, sizeof(T))) {
        return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
      }
      return gf_ara::core::Result<void>::Ok();
    }
#endif
    detail::TopicBus::Instance().Publish(path_.Key(), &sample, sizeof(T));
    return gf_ara::core::Result<void>::Ok();
  }

 private:
  ServicePath path_;
#if defined(GF_DDS_USE_CYCLONEDDS) && GF_DDS_USE_CYCLONEDDS
  CycloneWriter cyclone_{};
#endif
};

template <typename T>
class EventSubscriber {
 public:
  explicit EventSubscriber(ServicePath path) : path_(std::move(path)) {
    static_assert(std::is_trivially_copyable_v<T>,
                  "DDS Event payload must be trivially copyable (POD)");
#if defined(GF_DDS_USE_CYCLONEDDS) && GF_DDS_USE_CYCLONEDDS
    if (IsInitialized()) {
      cyclone_ = CycloneReader(path_);
    }
#endif
  }

  [[nodiscard]] const ServicePath& Path() const noexcept { return path_; }

  gf_ara::core::Result<std::optional<T>> Take() {
    if (!IsInitialized()) {
      return gf_ara::core::Result<std::optional<T>>::Err(
          gf_ara::core::ErrorCode::kNotAvailable);
    }
#if defined(GF_DDS_USE_CYCLONEDDS) && GF_DDS_USE_CYCLONEDDS
    if (cyclone_.Ok()) {
      T sample{};
      if (!cyclone_.Take(&sample, sizeof(T))) {
        return gf_ara::core::Result<std::optional<T>>::Ok(std::nullopt);
      }
      return gf_ara::core::Result<std::optional<T>>::Ok(std::optional<T>{sample});
    }
#endif
    T sample{};
    if (!detail::TopicBus::Instance().Take(path_.Key(), &sample, sizeof(T))) {
      return gf_ara::core::Result<std::optional<T>>::Ok(std::nullopt);
    }
    return gf_ara::core::Result<std::optional<T>>::Ok(std::optional<T>{sample});
  }

 private:
  ServicePath path_;
#if defined(GF_DDS_USE_CYCLONEDDS) && GF_DDS_USE_CYCLONEDDS
  CycloneReader cyclone_{};
#endif
};

}  // namespace gf_ara::com::binding::dds
