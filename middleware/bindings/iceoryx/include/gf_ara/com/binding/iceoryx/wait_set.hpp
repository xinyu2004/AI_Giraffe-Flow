#ifndef GF_ARA_COM_BINDING_ICEORYX_WAIT_SET_HPP
#define GF_ARA_COM_BINDING_ICEORYX_WAIT_SET_HPP

#include "gf_ara/com/binding/iceoryx/event.hpp"
#include "gf_ara/core/result.hpp"

#include "iceoryx_hoofs/internal/units/duration.hpp"
#include "iceoryx_posh/popo/subscriber.hpp"
#include "iceoryx_posh/popo/user_trigger.hpp"
#include "iceoryx_posh/popo/wait_set.hpp"

#include <cstdint>
#include <optional>
#include <vector>

namespace gf_ara::com::binding::iceoryx {

/// Multi-topic / timer wake owned by the APP process — middleware WaitSet surface.
/// Attach subscribers once; then TimedWait / Wait. Do not also call EventSubscriber::Wait
/// on the same subscriber (ALREADY_ATTACHED).
template <uint64_t Capacity = 16U>
class EventWaitSet {
 public:
  static constexpr uint64_t kCapacity = Capacity;

  EventWaitSet() = default;
  EventWaitSet(const EventWaitSet&) = delete;
  EventWaitSet& operator=(const EventWaitSet&) = delete;

  void MarkForDestruction() noexcept { waitset_.markForDestruction(); }

  template <typename T>
  gf_ara::core::Result<void> Attach(EventSubscriber<T>& sub, std::uint64_t notification_id = 0) {
    auto r = waitset_.attachState(sub.Native(), iox::popo::SubscriberState::HAS_DATA,
                                  notification_id);
    if (r.has_error()) {
      return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kBusy);
    }
    return gf_ara::core::Result<void>::Ok();
  }

  /// Attach any type exposing Native() → iox::popo::Subscriber<T>& (generated Proxy).
  template <typename Proxy>
  gf_ara::core::Result<void> AttachProxy(Proxy& proxy, std::uint64_t notification_id = 0) {
    auto r = waitset_.attachState(proxy.Native(), iox::popo::SubscriberState::HAS_DATA,
                                  notification_id);
    if (r.has_error()) {
      return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kBusy);
    }
    return gf_ara::core::Result<void>::Ok();
  }

  gf_ara::core::Result<void> AttachUserTrigger(iox::popo::UserTrigger& trigger,
                                               std::uint64_t notification_id = 0) {
    auto r = waitset_.attachEvent(trigger, notification_id);
    if (r.has_error()) {
      return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kBusy);
    }
    return gf_ara::core::Result<void>::Ok();
  }

  /// Returns notification ids that fired. Empty vector ⇒ timeout (TimedWait) or shutdown.
  std::vector<std::uint64_t> TimedWaitMs(std::uint32_t timeout_ms) {
    std::vector<std::uint64_t> ids;
    auto notifications =
        waitset_.timedWait(iox::units::Duration::fromMilliseconds(timeout_ms));
    ids.reserve(notifications.size());
    for (auto* info : notifications) {
      if (info) {
        ids.push_back(info->getNotificationId());
      }
    }
    return ids;
  }

  std::vector<std::uint64_t> Wait() {
    std::vector<std::uint64_t> ids;
    auto notifications = waitset_.wait();
    ids.reserve(notifications.size());
    for (auto* info : notifications) {
      if (info) {
        ids.push_back(info->getNotificationId());
      }
    }
    return ids;
  }

  [[nodiscard]] iox::popo::WaitSet<Capacity>& Native() noexcept { return waitset_; }

 private:
  iox::popo::WaitSet<Capacity> waitset_{};
};

}  // namespace gf_ara::com::binding::iceoryx

#endif
