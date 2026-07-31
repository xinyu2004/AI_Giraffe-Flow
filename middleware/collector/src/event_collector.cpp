#include "gf_ara/collector/event_collector.hpp"

#include <gf/osal/clock.hpp>

#include <iostream>

namespace gf_ara::collector {

EventCollector& EventCollector::Instance() {
  static EventCollector inst;
  return inst;
}

void EventCollector::Configure(CollectorConfig cfg) {
  std::lock_guard lock(mu_);
  if (cfg.max_entries == 0) {
    cfg.max_entries = 256;
  }
  cfg_ = std::move(cfg);
  if (ring_.size() > cfg_.max_entries) {
    ring_.erase(ring_.begin(),
                ring_.begin() + static_cast<std::ptrdiff_t>(ring_.size() - cfg_.max_entries));
  }
}

void EventCollector::ReportEvent(std::string_view source, std::string_view event_id,
                                 std::string_view detail, EventSeverity severity) {
  EventRecord rec;
  rec.t_ns = gf::osal::MonotonicNowNs();
  rec.source = std::string(source);
  rec.event_id = std::string(event_id);
  rec.detail = std::string(detail);
  rec.severity = severity;

  const bool store = cfg_.local_enabled &&
                     (cfg_.forward == "local_store" || cfg_.forward == "both");
  const bool fwd_cp = (cfg_.forward == "cp_dem" || cfg_.forward == "both");

  if (store) {
    std::lock_guard lock(mu_);
    ring_.push_back(rec);
    while (ring_.size() > cfg_.max_entries) {
      ring_.erase(ring_.begin());
    }
  }

  std::cout << "collector: event source=" << rec.source << " id=" << rec.event_id
            << " detail=" << rec.detail;
  if (fwd_cp) {
    std::cout << " forward=cp_dem(stub)";
  }
  std::cout << std::endl;
}

std::vector<EventRecord> EventCollector::Snapshot() const {
  std::lock_guard lock(mu_);
  return ring_;
}

std::size_t EventCollector::Size() const {
  std::lock_guard lock(mu_);
  return ring_.size();
}

void EventCollector::Clear() {
  std::lock_guard lock(mu_);
  ring_.clear();
}

}  // namespace gf_ara::collector
