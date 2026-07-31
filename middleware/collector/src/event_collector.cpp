#include "gf_ara/collector/event_collector.hpp"

#include <gf/osal/clock.hpp>

#include <cstdlib>
#include <fcntl.h>
#include <iostream>
#include <string>
#include <unistd.h>

#if defined(__linux__) || defined(__APPLE__)
#include <sys/file.h>
#endif

namespace gf_ara::collector {
namespace {

void AppendSharedStore(const EventRecord& rec) {
  const char* path = std::getenv("GF_COLLECTOR_STORE");
  if (path == nullptr || path[0] == '\0') {
    return;
  }
  const int fd = ::open(path, O_WRONLY | O_CREAT | O_APPEND, 0644);
  if (fd < 0) {
    std::cerr << "collector: shared store open failed path=" << path << std::endl;
    return;
  }
#if defined(__linux__) || defined(__APPLE__)
  if (::flock(fd, LOCK_EX) != 0) {
    ::close(fd);
    std::cerr << "collector: shared store flock failed path=" << path << std::endl;
    return;
  }
#endif
  const auto esc = [](std::string s) {
    for (char& c : s) {
      if (c == '"' || c == '\\' || c == '\n') {
        c = '_';
      }
    }
    return s;
  };
  const std::string line = std::string("{\"t_ns\":") + std::to_string(rec.t_ns) +
                           ",\"source\":\"" + esc(rec.source) + "\",\"id\":\"" + esc(rec.event_id) +
                           "\",\"detail\":\"" + esc(rec.detail) + "\",\"pid\":" +
                           std::to_string(static_cast<long>(::getpid())) + "}\n";
  const auto n = ::write(fd, line.data(), line.size());
  (void)n;
#if defined(__linux__) || defined(__APPLE__)
  ::flock(fd, LOCK_UN);
#endif
  ::close(fd);
}

}  // namespace

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

  AppendSharedStore(rec);

  std::cout << "collector: event source=" << rec.source << " id=" << rec.event_id
            << " detail=" << rec.detail;
  if (fwd_cp) {
    std::cout << " forward=cp_dem(stub)";
  }
  if (std::getenv("GF_COLLECTOR_STORE") != nullptr) {
    std::cout << " store=shared";
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
