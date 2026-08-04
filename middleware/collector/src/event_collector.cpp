#include "gf_ara/collector/event_collector.hpp"

#include <gf/osal/clock.hpp>
#include <gf_ara/per/key_value_storage.hpp>

#include <cstdlib>
#include <fcntl.h>
#include <iostream>
#include <regex>
#include <sstream>
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
    return;
  }
#if defined(__linux__) || defined(__APPLE__)
  if (::flock(fd, LOCK_EX) != 0) {
    ::close(fd);
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
  (void)::write(fd, line.data(), line.size());
#if defined(__linux__) || defined(__APPLE__)
  ::flock(fd, LOCK_UN);
#endif
  ::close(fd);
}

std::string DtcKey(std::uint32_t code) {
  std::ostringstream o;
  o << "DTC:" << std::hex << code;
  return o.str();
}

std::string EncodeDtc(const DtcEntry& e) {
  std::ostringstream o;
  o << std::hex << e.code << ',' << static_cast<unsigned>(e.status) << ',' << std::dec
    << e.occurrence << ',' << e.fdc << ',' << e.aging_remaining << ',' << e.freeze_t_ns << ','
    << e.freeze_blob;
  return o.str();
}

bool DecodeDtc(const std::string& s, DtcEntry& e) {
  std::istringstream in(s);
  char comma = 0;
  unsigned st = 0;
  if (!(in >> std::hex >> e.code >> comma >> st >> comma)) {
    return false;
  }
  e.status = static_cast<std::uint8_t>(st);
  if (!(in >> std::dec >> e.occurrence >> comma >> e.fdc >> comma >> e.aging_remaining >> comma >>
        e.freeze_t_ns >> comma)) {
    return false;
  }
  std::getline(in, e.freeze_blob);
  return true;
}

std::uint32_t ParseDtcHex(std::string_view s) {
  try {
    return static_cast<std::uint32_t>(std::stoul(std::string(s), nullptr, 0));
  } catch (...) {
    return 0;
  }
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
  EnsurePerLocked();
  LoadDtcsFromPerLocked();
}

void EventCollector::ConfigureFromYaml(std::string_view yaml_text) {
  CollectorConfig cfg = cfg_;
  const std::string text(yaml_text);
  std::smatch m;
  if (std::regex_search(text, m, std::regex(R"(forward:\s*(\S+))"))) {
    cfg.forward = m[1].str();
  }
  if (std::regex_search(text, m, std::regex(R"(max_entries:\s*(\d+))"))) {
    cfg.max_entries = static_cast<std::uint32_t>(std::stoul(m[1].str()));
  }
  // dtc_map entries: - event: phm/alive_timeout / dtc: 0x123456 / ...
  std::regex ent_re(
      R"(-?\s*event:\s*(\S+)[\s\S]*?dtc:\s*(\S+)(?:[\s\S]*?debounce_count:\s*(\d+))?(?:[\s\S]*?fdc_threshold:\s*(-?\d+))?(?:[\s\S]*?aging_cycles:\s*(\d+))?)");
  auto begin = std::sregex_iterator(text.begin(), text.end(), ent_re);
  auto end = std::sregex_iterator();
  for (auto it = begin; it != end; ++it) {
    DtcMapEntry e;
    e.dtc = ParseDtcHex((*it)[2].str());
    if ((*it)[3].matched) {
      e.debounce_count = static_cast<std::uint16_t>(std::stoul((*it)[3].str()));
    }
    if ((*it)[4].matched) {
      e.fdc_threshold = static_cast<std::int16_t>(std::stoi((*it)[4].str()));
    }
    if ((*it)[5].matched) {
      e.aging_cycles = static_cast<std::uint16_t>(std::stoul((*it)[5].str()));
    }
    if (e.dtc != 0) {
      cfg.dtc_map[(*it)[1].str()] = e;
    }
  }
  Configure(std::move(cfg));
}

void EventCollector::EnsurePerLocked() {
  auto& kv = gf_ara::per::KeyValueStorage::Instance();
  if (kv.IsOpen() && kv.InstanceName() == "dtc") {
    return;
  }
  const auto r = kv.Open("dtc");
  if (!r.HasValue() && !per_warned_) {
    per_warned_ = true;
    std::cerr << "collector: WARN persist disabled or per open failed "
                 "(runtime_modules may omit per; DTC RAM-only)\n";
  }
}

void EventCollector::LoadDtcsFromPerLocked() {
  auto& kv = gf_ara::per::KeyValueStorage::Instance();
  if (!kv.IsOpen()) {
    return;
  }
  const auto ctrl = kv.GetValue("DTC:CTRL");
  if (ctrl.HasValue()) {
    dtc_control_on_ = (ctrl.Value() != "0" && ctrl.Value() != "off");
  }
  // Scan known keys from current map + previously persisted: we keep in-memory; on Open
  // re-read by trying map DTCs and a small convention — also reload from Encode list via
  // walking debounce is insufficient. Store index key DTC:INDEX = comma hex codes.
  const auto idx = kv.GetValue("DTC:INDEX");
  if (!idx.HasValue()) {
    return;
  }
  std::istringstream in(idx.Value());
  std::string tok;
  while (std::getline(in, tok, ',')) {
    if (tok.empty()) {
      continue;
    }
    const auto code = ParseDtcHex(tok);
    const auto raw = kv.GetValue(DtcKey(code));
    if (!raw.HasValue() || raw.Value().empty()) {
      continue;
    }
    DtcEntry e;
    if (DecodeDtc(raw.Value(), e)) {
      dtcs_[e.code] = e;
    }
  }
}

void EventCollector::PersistCtrlLocked() {
  EnsurePerLocked();
  auto& kv = gf_ara::per::KeyValueStorage::Instance();
  if (!kv.IsOpen()) {
    return;
  }
  (void)kv.SetValue("DTC:CTRL", dtc_control_on_ ? "1" : "0");
}

void EventCollector::PersistDtcLocked(const DtcEntry& e) {
  EnsurePerLocked();
  auto& kv = gf_ara::per::KeyValueStorage::Instance();
  if (!kv.IsOpen()) {
    return;
  }
  (void)kv.SetValue(DtcKey(e.code), EncodeDtc(e));
  std::ostringstream idx;
  bool first = true;
  for (const auto& kv_pair : dtcs_) {
    if (!first) {
      idx << ',';
    }
    first = false;
    idx << std::hex << kv_pair.first;
  }
  (void)kv.SetValue("DTC:INDEX", idx.str());
}

void EventCollector::DeleteDtcPerLocked(std::uint32_t code) {
  EnsurePerLocked();
  auto& kv = gf_ara::per::KeyValueStorage::Instance();
  if (!kv.IsOpen()) {
    return;
  }
  (void)kv.SetValue(DtcKey(code), "");  // empty tombstone; filter on load
  std::ostringstream idx;
  bool first = true;
  for (const auto& kv_pair : dtcs_) {
    if (!first) {
      idx << ',';
    }
    first = false;
    idx << std::hex << kv_pair.first;
  }
  (void)kv.SetValue("DTC:INDEX", idx.str());
}

void EventCollector::ApplyFaultLocked(std::string_view event_id, std::string_view detail) {
  const auto it = cfg_.dtc_map.find(std::string(event_id));
  if (it == cfg_.dtc_map.end()) {
    return;
  }
  if (!dtc_control_on_) {
    return;
  }
  const DtcMapEntry& map = it->second;
  const std::string eid(event_id);
  const std::uint64_t now = gf::osal::MonotonicNowNs();

  auto& hits = debounce_hits_[eid];
  auto& first_ns = debounce_first_ns_[eid];
  if (hits == 0) {
    first_ns = now;
  }
  ++hits;
  if (map.debounce_ms > 0 && (now - first_ns) > static_cast<std::uint64_t>(map.debounce_ms) * 1000000ULL) {
    hits = 1;
    first_ns = now;
  }
  if (hits < map.debounce_count) {
    return;
  }
  hits = 0;

  DtcEntry& e = dtcs_[map.dtc];
  e.code = map.dtc;
  e.fdc = static_cast<std::int16_t>(e.fdc + map.fdc_inc);
  if (e.fdc >= map.fdc_threshold) {
    e.status |= DtcStatus::kTestFailed | DtcStatus::kPending;
    if ((e.status & DtcStatus::kConfirmed) == 0) {
      e.status |= DtcStatus::kConfirmed;
      ++e.occurrence;
      e.aging_remaining = map.aging_cycles;
      e.freeze_t_ns = now;
      if (freeze_capture_) {
        e.freeze_blob = freeze_capture_(map.dtc);
      } else {
        e.freeze_blob = std::string("event=") + eid + ";detail=" + std::string(detail);
      }
    }
    e.fdc = map.fdc_threshold;
  }
  PersistDtcLocked(e);
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

  {
    std::lock_guard lock(mu_);
    if (store) {
      ring_.push_back(rec);
      while (ring_.size() > cfg_.max_entries) {
        ring_.erase(ring_.begin());
      }
    }
    if (severity >= EventSeverity::kWarn) {
      ApplyFaultLocked(event_id, detail);
    }
  }

  AppendSharedStore(rec);

  std::cout << "collector: event source=" << rec.source << " id=" << rec.event_id
            << " detail=" << rec.detail;
  if (fwd_cp) {
    std::cout << " forward=cp_dem(stub)";
  }
  std::cout << std::endl;
}

void EventCollector::NotifyOperationCycle() {
  std::lock_guard lock(mu_);
  // Assume tests passed this cycle unless re-failed before next cycle.
  for (auto& kv : dtcs_) {
    DtcEntry& e = kv.second;
    e.status = static_cast<std::uint8_t>(e.status & ~DtcStatus::kTestFailed);
    if (e.fdc > 0) {
      --e.fdc;
    }
    if (e.fdc == 0) {
      e.status = static_cast<std::uint8_t>(e.status & ~DtcStatus::kPending);
    }
  }
  std::vector<std::uint32_t> erase;
  for (auto& kv : dtcs_) {
    DtcEntry& e = kv.second;
    if ((e.status & DtcStatus::kConfirmed) == 0) {
      PersistDtcLocked(e);
      continue;
    }
    if (e.aging_remaining > 0) {
      --e.aging_remaining;
      if (e.aging_remaining == 0) {
        erase.push_back(e.code);
      } else {
        PersistDtcLocked(e);
      }
    }
  }
  for (auto code : erase) {
    dtcs_.erase(code);
    DeleteDtcPerLocked(code);
  }
}

void EventCollector::SetDtcControlEnabled(bool enabled) {
  std::lock_guard lock(mu_);
  dtc_control_on_ = enabled;
  PersistCtrlLocked();
}

bool EventCollector::DtcControlEnabled() const noexcept {
  std::lock_guard lock(mu_);
  return dtc_control_on_;
}

std::vector<DtcEntry> EventCollector::ListDtcs(std::uint8_t status_mask) const {
  std::lock_guard lock(mu_);
  std::vector<DtcEntry> out;
  for (const auto& kv : dtcs_) {
    if (status_mask == 0xFF || (kv.second.status & status_mask) != 0) {
      out.push_back(kv.second);
    }
  }
  return out;
}

std::size_t EventCollector::CountDtcs(std::uint8_t status_mask) const {
  return ListDtcs(status_mask).size();
}

bool EventCollector::ClearDtc(std::uint32_t group_or_code) {
  std::lock_guard lock(mu_);
  if (group_or_code == 0xFFFFFF) {
    const auto keys = [&] {
      std::vector<std::uint32_t> k;
      for (const auto& kv : dtcs_) {
        k.push_back(kv.first);
      }
      return k;
    }();
    for (auto code : keys) {
      dtcs_.erase(code);
      DeleteDtcPerLocked(code);
    }
    return true;
  }
  const auto it = dtcs_.find(group_or_code);
  if (it == dtcs_.end()) {
    return false;
  }
  dtcs_.erase(it);
  DeleteDtcPerLocked(group_or_code);
  return true;
}

bool EventCollector::GetFreezeFrame(std::uint32_t dtc, std::string& blob_out,
                                    std::uint64_t& t_ns_out) const {
  std::lock_guard lock(mu_);
  const auto it = dtcs_.find(dtc);
  if (it == dtcs_.end() || it->second.freeze_blob.empty()) {
    return false;
  }
  blob_out = it->second.freeze_blob;
  t_ns_out = it->second.freeze_t_ns;
  return true;
}

void EventCollector::SetFreezeCapture(std::function<std::string(std::uint32_t)> capture) {
  std::lock_guard lock(mu_);
  freeze_capture_ = std::move(capture);
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
  debounce_hits_.clear();
  debounce_first_ns_.clear();
}

}  // namespace gf_ara::collector
