#ifndef GF_ARA_LOG_DLT_SINK_HPP
#define GF_ARA_LOG_DLT_SINK_HPP

#include "gf_ara/log/logger.hpp"

#include <string>
#include <string_view>

namespace gf_ara::log {

/// COVESA libdlt sink (no-op when GF_HAVE_DLT is off).
/// Bounded context table; never grows without limit (BL-MEM-BOUND).
/// Does not block when daemon is absent (nonblocking open /tmp/dlt; skip stale FIFO).
class DltSink {
 public:
  static DltSink& Instance();

  /// Register DLT application when daemon IPC is up. Safe to call repeatedly.
  void Configure(std::string_view app_id, std::string_view description);

  /// BL-MEM-BOUND: max DLT context handles (default 64).
  void SetMaxContexts(std::size_t n) noexcept;

  [[nodiscard]] bool Ready() const noexcept { return ready_; }

  void Write(std::string_view ctx, LogLevel level, std::string_view msg);

 private:
  DltSink() = default;
  bool ready_{false};
  std::size_t max_contexts_{64};
  std::string app_id_{"GFAP"};
  std::string description_{"Giraffe Flow"};
};

}  // namespace gf_ara::log

#endif
