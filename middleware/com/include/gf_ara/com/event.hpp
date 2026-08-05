#ifndef GF_ARA_COM_EVENT_HPP
#define GF_ARA_COM_EVENT_HPP

#include "gf_ara/com/service_path.hpp"
#include "gf_ara/core/result.hpp"

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <mutex>
#include <optional>
#include <queue>
#include <string>
#include <type_traits>
#include <unordered_map>
#include <vector>

namespace gf_ara::com {

/// In-process Event transport for P0 smoke (no RouDi).
/// Real IPC will use bindings/iceoryx with the same Publisher/Subscriber surface.
class LoopbackBus {
 public:
  static LoopbackBus& Instance() {
    static LoopbackBus bus;
    return bus;
  }

  /// BL-MEM-BOUND (defaults: depth=16, keys=64).
  void ConfigureBounds(std::size_t queue_depth, std::size_t max_topic_keys) {
    std::lock_guard<std::mutex> lock(mu_);
    max_depth_ = queue_depth == 0 ? 16 : queue_depth;
    max_keys_ = max_topic_keys == 0 ? 64 : max_topic_keys;
  }

  void Publish(const std::string& key, std::vector<std::uint8_t> bytes) {
    std::lock_guard<std::mutex> lock(mu_);
    if (queues_.find(key) == queues_.end() && queues_.size() >= max_keys_) {
      // Drop an empty or arbitrary topic to stay bounded.
      for (auto it = queues_.begin(); it != queues_.end(); ++it) {
        if (it->second.empty()) {
          queues_.erase(it);
          break;
        }
      }
      if (queues_.size() >= max_keys_) {
        queues_.erase(queues_.begin());
      }
    }
    auto& q = queues_[key];
    if (q.size() >= max_depth_) {
      q.pop();
    }
    q.push(std::move(bytes));
  }

  std::optional<std::vector<std::uint8_t>> Take(const std::string& key) {
    std::lock_guard<std::mutex> lock(mu_);
    auto it = queues_.find(key);
    if (it == queues_.end() || it->second.empty()) {
      return std::nullopt;
    }
    auto bytes = std::move(it->second.front());
    it->second.pop();
    return bytes;
  }

  void Clear() {
    std::lock_guard<std::mutex> lock(mu_);
    queues_.clear();
  }

 private:
  LoopbackBus() = default;
  std::mutex mu_;
  std::size_t max_depth_{16};
  std::size_t max_keys_{64};
  std::unordered_map<std::string, std::queue<std::vector<std::uint8_t>>> queues_;
};

template <typename T>
class EventPublisher {
 public:
  explicit EventPublisher(ServicePath path) : path_(std::move(path)) {}

  [[nodiscard]] const ServicePath& Path() const noexcept { return path_; }

  gf_ara::core::Result<void> Publish(const T& sample) {
    static_assert(std::is_trivially_copyable_v<T>,
                  "P0 Event payload must be trivially copyable (POD)");
    std::vector<std::uint8_t> bytes(sizeof(T));
    std::memcpy(bytes.data(), &sample, sizeof(T));
    LoopbackBus::Instance().Publish(path_.Key(), std::move(bytes));
    return gf_ara::core::Result<void>::Ok();
  }

 private:
  ServicePath path_;
};

template <typename T>
class EventSubscriber {
 public:
  explicit EventSubscriber(ServicePath path) : path_(std::move(path)) {}

  [[nodiscard]] const ServicePath& Path() const noexcept { return path_; }

  gf_ara::core::Result<std::optional<T>> Take() {
    static_assert(std::is_trivially_copyable_v<T>,
                  "P0 Event payload must be trivially copyable (POD)");
    auto bytes = LoopbackBus::Instance().Take(path_.Key());
    if (!bytes) {
      return gf_ara::core::Result<std::optional<T>>::Ok(std::nullopt);
    }
    if (bytes->size() != sizeof(T)) {
      return gf_ara::core::Result<std::optional<T>>::Err(
          gf_ara::core::ErrorCode::kInvalidArgument);
    }
    T sample{};
    std::memcpy(&sample, bytes->data(), sizeof(T));
    return gf_ara::core::Result<std::optional<T>>::Ok(std::optional<T>{sample});
  }

 private:
  ServicePath path_;
};

}  // namespace gf_ara::com

#endif
