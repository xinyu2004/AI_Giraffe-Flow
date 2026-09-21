#ifndef GF_ARA_COM_EVENT_HPP
#define GF_ARA_COM_EVENT_HPP

#include "gf_ara/com/service_path.hpp"
#include "gf_ara/core/result.hpp"

#include <chrono>
#include <condition_variable>
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
/// Real IPC uses bindings/iceoryx with the same Publisher/Subscriber surface.
/// Publish wakes Wait / WaitAny (SOA: middleware owns wake, not app sleep).
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
    {
      std::lock_guard<std::mutex> lock(mu_);
      if (queues_.find(key) == queues_.end() && queues_.size() >= max_keys_) {
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
    cv_.notify_all();
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

  [[nodiscard]] bool HasPending(const std::string& key) const {
    std::lock_guard<std::mutex> lock(mu_);
    auto it = queues_.find(key);
    return it != queues_.end() && !it->second.empty();
  }

  /// Block until `key` has a sample, or timeout. Does not Take.
  /// timeout_ms == 0 → poll once; nullopt → wait forever.
  bool Wait(const std::string& key, std::optional<std::uint32_t> timeout_ms) {
    std::unique_lock<std::mutex> lock(mu_);
    auto ready = [&] {
      auto it = queues_.find(key);
      return it != queues_.end() && !it->second.empty();
    };
    if (ready()) {
      return true;
    }
    if (!timeout_ms.has_value()) {
      cv_.wait(lock, ready);
      return true;
    }
    if (*timeout_ms == 0) {
      return false;
    }
    return cv_.wait_for(lock, std::chrono::milliseconds(*timeout_ms), ready);
  }

  /// Block until any key in `keys` has a sample, or timeout.
  bool WaitAny(const std::vector<std::string>& keys, std::optional<std::uint32_t> timeout_ms) {
    std::unique_lock<std::mutex> lock(mu_);
    auto ready = [&] {
      for (const auto& k : keys) {
        auto it = queues_.find(k);
        if (it != queues_.end() && !it->second.empty()) {
          return true;
        }
      }
      return false;
    };
    if (ready()) {
      return true;
    }
    if (!timeout_ms.has_value()) {
      cv_.wait(lock, ready);
      return true;
    }
    if (*timeout_ms == 0) {
      return false;
    }
    return cv_.wait_for(lock, std::chrono::milliseconds(*timeout_ms), ready);
  }

  void Clear() {
    std::lock_guard<std::mutex> lock(mu_);
    queues_.clear();
  }

 private:
  LoopbackBus() = default;
  mutable std::mutex mu_;
  std::condition_variable cv_;
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

  [[nodiscard]] bool HasData() const { return LoopbackBus::Instance().HasPending(path_.Key()); }

  /// Wait until a sample is pending (does not Take). nullopt = forever.
  gf_ara::core::Result<void> Wait(std::optional<std::uint32_t> timeout_ms = std::nullopt) {
    if (LoopbackBus::Instance().Wait(path_.Key(), timeout_ms)) {
      return gf_ara::core::Result<void>::Ok();
    }
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kTimeout);
  }

 private:
  ServicePath path_;
};

}  // namespace gf_ara::com

#endif
