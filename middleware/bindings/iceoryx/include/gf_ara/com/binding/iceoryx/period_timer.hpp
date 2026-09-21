#ifndef GF_ARA_COM_BINDING_ICEORYX_PERIOD_TIMER_HPP
#define GF_ARA_COM_BINDING_ICEORYX_PERIOD_TIMER_HPP

#include "gf_ara/com/binding/iceoryx/wait_set.hpp"
#include "gf_ara/core/result.hpp"

#include "iceoryx_posh/popo/user_trigger.hpp"

#include <atomic>
#include <chrono>
#include <cstdint>
#include <thread>

namespace gf_ara::com::binding::iceoryx {

/// Middleware-owned period wake for publish_policy `trigger: period`.
/// Spawns a thread that fires UserTrigger into an EventWaitSet — apps must not sleep
/// their own period clocks.
class PeriodTimer {
 public:
  PeriodTimer() = default;
  PeriodTimer(const PeriodTimer&) = delete;
  PeriodTimer& operator=(const PeriodTimer&) = delete;

  ~PeriodTimer() { Stop(); }

  template <uint64_t Cap>
  gf_ara::core::Result<void> Start(EventWaitSet<Cap>& waitset, std::uint64_t notification_id,
                                   std::uint32_t period_ms) {
    if (period_ms == 0 || running_.load()) {
      return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kInvalidArgument);
    }
    auto attached = waitset.AttachUserTrigger(trigger_, notification_id);
    if (!attached) {
      return attached;
    }
    period_ms_ = period_ms;
    running_.store(true);
    thr_ = std::thread([this] {
      while (running_.load()) {
        std::this_thread::sleep_for(std::chrono::milliseconds(period_ms_));
        if (!running_.load()) {
          break;
        }
        trigger_.trigger();
      }
    });
    return gf_ara::core::Result<void>::Ok();
  }

  void Stop() {
    running_.store(false);
    trigger_.trigger();  // unblock waiters
    if (thr_.joinable()) {
      thr_.join();
    }
  }

  [[nodiscard]] iox::popo::UserTrigger& Native() noexcept { return trigger_; }

 private:
  iox::popo::UserTrigger trigger_{};
  std::atomic<bool> running_{false};
  std::uint32_t period_ms_{0};
  std::thread thr_{};
};

}  // namespace gf_ara::com::binding::iceoryx

#endif
