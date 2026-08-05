#include "gf_ara/runtime/process_bringup.hpp"

#include <gf_ara/collector/event_collector.hpp>
#include <gf_ara/com/event.hpp>
#include <gf_ara/log/logger.hpp>
#include <gf_ara/per/key_value_storage.hpp>

#include <chrono>
#include <cstdlib>
#include <fstream>
#include <regex>
#include <sstream>

namespace gf_ara::runtime {
namespace {

std::string ReadFile(const std::string& path) {
  std::ifstream in(path);
  if (!in) {
    return {};
  }
  std::ostringstream ss;
  ss << in.rdbuf();
  return ss.str();
}

std::uint32_t EnvU32(const char* key, std::uint32_t fallback) {
  const char* v = std::getenv(key);
  if (!v || !*v) {
    return fallback;
  }
  return static_cast<std::uint32_t>(std::strtoul(v, nullptr, 10));
}

std::uint32_t FaultMs() {
  if (const char* a = std::getenv("GF_PHM_FAULT_MS"); a && *a) {
    return EnvU32("GF_PHM_FAULT_MS", 0);
  }
  return EnvU32("GF_PHM_FAULT_INJECT_MS", 0);
}

bool EnvFlag(const char* key) {
  const char* v = std::getenv(key);
  return v && (*v == '1' || *v == 'y' || *v == 'Y' || *v == 't' || *v == 'T');
}

/** Process-local monotonic ms for FuSa latency parsing (t_ms=…). */
std::uint64_t MonoMs() {
  using clock = std::chrono::steady_clock;
  static const auto t0 = clock::now();
  return static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::milliseconds>(clock::now() - t0).count());
}

const char* StatusName(gf_ara::phm::CheckpointStatus st) {
  using gf_ara::phm::CheckpointStatus;
  switch (st) {
    case CheckpointStatus::kOk:
      return "Ok";
    case CheckpointStatus::kAliveMissed:
      return "AliveMissed";
    case CheckpointStatus::kDeadlineMissed:
      return "DeadlineMissed";
    case CheckpointStatus::kLogicalFault:
      return "LogicalFault";
  }
  return "?";
}

}  // namespace

std::string PlatformDir() {
  if (const char* d = std::getenv("GF_PLATFORM_DIR"); d && *d) {
    std::string out{d};
    while (!out.empty() && out.back() == '/') {
      out.pop_back();
    }
    if (ReadFile(out + "/exec.yaml").empty() &&
        !ReadFile(out + "/platform/exec.yaml").empty()) {
      out += "/platform";
    }
    return out;
  }
  return {};
}

ExecProcessConfig LoadExecProcess(std::string_view process_name) {
  ExecProcessConfig cfg;
  const std::string dir = PlatformDir();
  if (dir.empty()) {
    cfg.found = true;
    cfg.execution_client = true;
    cfg.function_group = "MachineFG";
    return cfg;
  }
  const std::string text = ReadFile(dir + "/exec.yaml");
  if (text.empty()) {
    gf_ara::log::Logger::Instance().Error(
        "runtime", "cannot read " + dir + "/exec.yaml");
    return cfg;
  }

  const std::regex name_re(std::string(R"(-\s*name:\s*)") + std::string(process_name) +
                           R"(\b)");
  std::smatch m;
  if (!std::regex_search(text, m, name_re)) {
    return cfg;
  }
  cfg.found = true;
  const auto start = static_cast<std::size_t>(m.position(0));
  const std::string window =
      text.substr(start, std::min<std::size_t>(500, text.size() - start));

  std::smatch km;
  if (std::regex_search(window, km, std::regex(R"(function_group:\s*(\S+))"))) {
    cfg.function_group = km[1].str();
  }
  if (std::regex_search(
          window, km,
          std::regex(R"(execution_client:\s*(true|false))", std::regex::icase))) {
    cfg.execution_client = (km[1].str() != "false" && km[1].str() != "False");
  }
  return cfg;
}

PhmEntityConfig LoadPhmEntity(std::string_view process_name) {
  PhmEntityConfig cfg;
  const std::string dir = PlatformDir();
  if (dir.empty()) {
    return cfg;
  }
  const std::string text = ReadFile(dir + "/phm.yaml");
  if (text.empty()) {
    gf_ara::log::Logger::Instance().Error(
        "runtime", "cannot read " + dir + "/phm.yaml");
    return cfg;
  }

  const std::regex proc_re(std::string(R"(process:\s*)") + std::string(process_name) +
                           R"(\b)");
  std::smatch m;
  if (!std::regex_search(text, m, proc_re)) {
    return cfg;
  }
  const auto proc_pos = static_cast<std::size_t>(m.position(0));
  const std::size_t block_start = (proc_pos > 120) ? proc_pos - 120 : 0;
  const std::string before = text.substr(block_start, proc_pos - block_start);
  const std::string after =
      text.substr(proc_pos, std::min<std::size_t>(300, text.size() - proc_pos));

  cfg.found = true;
  std::smatch id_m;
  std::string id_region = before;
  std::string last_id;
  auto search_start = id_region.cbegin();
  while (std::regex_search(search_start, id_region.cend(), id_m,
                           std::regex(R"(id:\s*(\S+))"))) {
    last_id = id_m[1].str();
    search_start = id_m.suffix().first;
  }
  cfg.id = last_id.empty() ? (std::string(process_name) + "_alive") : last_id;

  std::smatch p_m;
  if (std::regex_search(after, p_m, std::regex(R"(alive_period_ms:\s*(\d+))"))) {
    cfg.alive_period_ms = static_cast<std::uint32_t>(std::stoul(p_m[1].str()));
  }
  if (std::regex_search(after, p_m, std::regex(R"(alive_timeout_ms:\s*(\d+))"))) {
    cfg.alive_timeout_ms = static_cast<std::uint32_t>(std::stoul(p_m[1].str()));
  }
  if (std::regex_search(after, p_m, std::regex(R"(on_failure:\s*(\S+))"))) {
    cfg.on_failure = p_m[1].str();
  }
  return cfg;
}

void LoadCollectorConfig() {
  const std::string dir = PlatformDir();
  if (dir.empty()) {
    return;
  }
  const std::string text = ReadFile(dir + "/collector.yaml");
  if (text.empty()) {
    gf_ara::collector::EventCollector::Instance().Configure({});
    return;
  }
  // Full scrape incl. dtc_map (same path as gf_doip_ota_server).
  gf_ara::collector::EventCollector::Instance().ConfigureFromYaml(text);
  const auto& cfg = gf_ara::collector::EventCollector::Instance().Config();
  gf_ara::log::Logger::Instance().Info(
      "collector",
      "configured forward=" + cfg.forward + " max_entries=" + std::to_string(cfg.max_entries) +
          " dtc_map=" + std::to_string(cfg.dtc_map.size()));
}

void LoadLogConfig() {
  const std::string dir = PlatformDir();
  auto& log = gf_ara::log::Logger::Instance();
  if (!dir.empty()) {
    const std::string text = ReadFile(dir + "/log.yaml");
    if (!text.empty()) {
      log.ConfigureFromYaml(text);
    }
  }
  log.ApplyEnvFileSink();
  log.Info("runtime",
           std::string("log configured default_level=") +
               gf_ara::log::Logger::ToString(log.Config().default_level) +
               (log.Config().file_path.empty() ? "" : " file=" + log.Config().file_path));
}

void LoadMemoryBounds() {
  const std::string dir = PlatformDir();
  if (dir.empty()) {
    return;
  }
  const std::string text = ReadFile(dir + "/bounds.yaml");
  if (text.empty()) {
    return;
  }
  std::uint32_t com_depth = 16;
  std::uint32_t com_keys = 64;
  std::uint32_t per_keys = 1024;
  std::uint32_t per_val = 65536;
  std::uint32_t dlt_ctx = 0;
  std::smatch m;
  if (std::regex_search(text, m, std::regex(R"(com:\s*[\s\S]*?queue_depth:\s*(\d+))"))) {
    com_depth = static_cast<std::uint32_t>(std::stoul(m[1].str()));
  }
  if (std::regex_search(text, m, std::regex(R"(com:\s*[\s\S]*?max_topic_keys:\s*(\d+))"))) {
    com_keys = static_cast<std::uint32_t>(std::stoul(m[1].str()));
  }
  if (std::regex_search(text, m, std::regex(R"(per:\s*[\s\S]*?max_keys:\s*(\d+))"))) {
    per_keys = static_cast<std::uint32_t>(std::stoul(m[1].str()));
  }
  if (std::regex_search(text, m, std::regex(R"(per:\s*[\s\S]*?max_value_bytes:\s*(\d+))"))) {
    per_val = static_cast<std::uint32_t>(std::stoul(m[1].str()));
  }
  if (std::regex_search(text, m, std::regex(R"(dlt:\s*[\s\S]*?max_contexts:\s*(\d+))"))) {
    dlt_ctx = static_cast<std::uint32_t>(std::stoul(m[1].str()));
  }
  gf_ara::com::LoopbackBus::Instance().ConfigureBounds(com_depth, com_keys);
  gf_ara::per::KeyValueStorage::Instance().ConfigureBounds(per_keys, per_val);
  if (dlt_ctx > 0) {
    auto& log = gf_ara::log::Logger::Instance();
    auto cfg = log.Config();
    cfg.dlt_max_contexts = dlt_ctx;
    log.Configure(cfg);
  }
  gf_ara::log::Logger::Instance().Info(
      "runtime",
      "mem bounds com_depth=" + std::to_string(com_depth) +
          " com_keys=" + std::to_string(com_keys) + " per_keys=" + std::to_string(per_keys) +
          " per_val=" + std::to_string(per_val) +
          (dlt_ctx ? " dlt_ctx=" + std::to_string(dlt_ctx) : ""));
}

bool ProcessSupervisor::Start(std::string_view process_name) {
  process_ = std::string(process_name);
  // Log first so subsequent bring-up steps use Logger sinks (incl. shared file).
  LoadLogConfig();
  LoadMemoryBounds();
  auto& log = gf_ara::log::Logger::Instance();
  log.Info("runtime", "bring-up begin process=" + process_);
  LoadCollectorConfig();

  const auto exec_cfg = LoadExecProcess(process_name);
  if (PlatformDir().empty()) {
    log.Warn("runtime", "GF_PLATFORM_DIR unset — using Offer defaults for " + process_);
  } else if (!exec_cfg.found) {
    log.Error("runtime", "process not in exec.yaml: " + process_);
    return false;
  } else if (!exec_cfg.execution_client) {
    log.Error("runtime", "execution_client=false for " + process_);
    return false;
  }

  function_group_ =
      exec_cfg.function_group.empty() ? "MachineFG" : exec_cfg.function_group;

  using gf_ara::sm::FunctionGroupState;
  using gf_ara::sm::StateClient;
  log.Info("sm", "EnsureGroup " + function_group_ + " → Running");
  StateClient::EnsureGroup(function_group_, FunctionGroupState::kRunning);
  StateClient::RequestTransition(function_group_, FunctionGroupState::kRunning);
  log.Info("sm", "state=" + std::string(gf_ara::sm::ToString(StateClient::GetState(function_group_))) +
                     " fg=" + function_group_);

  using gf_ara::exec::ExecutionClient;
  using gf_ara::exec::ExecutionManager;
  using gf_ara::exec::ExecutionState;
  log.Info("exec", "StartProcess/Offer process=" + process_);
  ExecutionManager::StartProcess(process_);
  if (!ExecutionClient::Offer(process_)) {
    log.Error("exec", "Offer failed for " + process_);
    return false;
  }
  if (!ExecutionClient::ReportExecutionState(ExecutionState::kRunning)) {
    log.Error("exec", "Report Running failed for " + process_);
    return false;
  }
  // Keep "Offer→Running" substring for SIL verify greps.
  log.Info("runtime", "t_ms=" + std::to_string(MonoMs()) + " Offer→Running process=" + process_ +
                          " fg=" + function_group_ + " sm=" +
                          gf_ara::sm::ToString(StateClient::GetState(function_group_)));

  const auto phm_cfg = LoadPhmEntity(process_name);
  if (phm_cfg.found) {
    entity_.emplace(phm_cfg.id);
    alive_period_ms_ = phm_cfg.alive_period_ms;
    on_failure_ = phm_cfg.on_failure.empty() ? "log" : phm_cfg.on_failure;
    entity_->Configure(phm_cfg.alive_period_ms, phm_cfg.alive_timeout_ms);
    next_alive_ = std::chrono::steady_clock::now();
    log.Info("phm", "entity=" + phm_cfg.id + " period_ms=" + std::to_string(phm_cfg.alive_period_ms) +
                        " timeout_ms=" + std::to_string(phm_cfg.alive_timeout_ms) +
                        " on_failure=" + on_failure_);

    const auto fault_ms = FaultMs();
    if (fault_ms > 0) {
      fault_pending_ = true;
      log.Info("phm", "t_ms=" + std::to_string(MonoMs()) + " FAULT inject armed for " +
                          std::to_string(fault_ms) + " ms after first Alive");
    }
  } else if (!PlatformDir().empty()) {
    log.Info("phm", "no entity for " + process_ + " (ok)");
  }
  log.Info("runtime", "bring-up done process=" + process_);
  return true;
}

void ProcessSupervisor::SoftRestartViaEm(const char* reason) {
  using gf_ara::exec::ExecutionClient;
  using gf_ara::exec::ExecutionManager;
  using gf_ara::exec::ExecutionState;

  ExecutionManager::RequestRestart(process_, reason);
  auto& log = gf_ara::log::Logger::Instance();
  if (!ExecutionClient::Offer(process_) ||
      !ExecutionClient::ReportExecutionState(ExecutionState::kRunning)) {
    log.Error("exec", "em soft restart Offer/Running failed process=" + process_);
    return;
  }
  ExecutionManager::ConsumeRestartPending(process_);
  if (entity_) {
    entity_->SetPaused(false);
    entity_->ReportLogical(true);
    entity_->ReportAlive();
  }
  fault_active_ = false;
  fault_pending_ = false;
  last_status_ = gf_ara::phm::CheckpointStatus::kOk;
  ++em_restart_count_;
  next_alive_ = std::chrono::steady_clock::now() +
                std::chrono::milliseconds(alive_period_ms_);
  log.Info("exec", "t_ms=" + std::to_string(MonoMs()) + " em soft_restart process=" + process_ +
                       " count=" + std::to_string(ExecutionManager::RestartCount(process_)));
}

void ProcessSupervisor::RequestOsEmRestart(const char* reason) {
  using gf_ara::exec::ExecutionManager;
  ExecutionManager::RequestRestart(process_, reason);
  ++em_restart_count_;
  exit_for_em_restart_ = true;
  gf_ara::log::Logger::Instance().Info(
      "exec", "t_ms=" + std::to_string(MonoMs()) + " em os_restart_exit process=" + process_ +
                  " code=" + std::to_string(gf_ara::exec::kEmRestartExitCode) +
                  " reason=" + reason);
}

void ProcessSupervisor::OnFault(gf_ara::phm::CheckpointStatus st) {
  const char* reason = StatusName(st);
  ++miss_count_;
  auto& log = gf_ara::log::Logger::Instance();
  log.Error("phm", "t_ms=" + std::to_string(MonoMs()) + " " + reason +
                       " entity=" + std::string(entity_->Name()));

  gf_ara::collector::EventCollector::Instance().ReportEvent(
      "phm", reason, std::string("entity=") + std::string(entity_->Name()),
      gf_ara::collector::EventSeverity::kError);

  if (on_failure_ == "restart") {
    // Default under EM daemon: exit 75 for OS relaunch. Soft path if forced or unmanaged.
    const bool soft = EnvFlag("GF_EM_SOFT_RESTART") || !EnvFlag("GF_EM_MANAGED");
    if (soft) {
      SoftRestartViaEm(reason);
    } else {
      RequestOsEmRestart(reason);
    }
    return;
  }

  if (on_failure_ == "notify_sm") {
    const bool enter_upd = EnvFlag("GF_SM_ENTER_UPDATING_ON_FAULT");
    gf_ara::sm::StateClient::NotifyHealthFault(function_group_, entity_->Name(), reason,
                                               enter_upd);
    if (enter_upd && entity_) {
      entity_->SetPaused(true);
      log.Info("phm", "paused (sm Updating) entity=" + std::string(entity_->Name()));
    }
    return;
  }
}

void ProcessSupervisor::Tick() {
  if (!entity_) {
    return;
  }

  // Resume Alive when SM left Updating
  if (entity_->Paused()) {
    using gf_ara::sm::FunctionGroupState;
    using gf_ara::sm::StateClient;
    if (StateClient::GetState(function_group_) != FunctionGroupState::kUpdating) {
      entity_->SetPaused(false);
      gf_ara::log::Logger::Instance().Info(
          "phm", "resume entity=" + std::string(entity_->Name()));
    }
  }

  const auto now = std::chrono::steady_clock::now();
  auto& log = gf_ara::log::Logger::Instance();

  if (fault_pending_ && ever_alive_) {
    const auto fault_ms = FaultMs();
    fault_until_ = now + std::chrono::milliseconds(fault_ms);
    fault_pending_ = false;
    fault_active_ = true;
    log.Info("phm", "t_ms=" + std::to_string(MonoMs()) +
                        " FAULT inject begin entity=" + std::string(entity_->Name()));
  }

  if (fault_active_ && now >= fault_until_) {
    log.Info("phm", "t_ms=" + std::to_string(MonoMs()) +
                        " fault window ended entity=" + std::string(entity_->Name()));
    fault_active_ = false;
  }

  if (!fault_active_ && !entity_->Paused() && now >= next_alive_) {
    entity_->ReportAlive();
    ever_alive_ = true;
    next_alive_ = now + std::chrono::milliseconds(alive_period_ms_);
  }

  const auto st = entity_->Evaluate();
  if (st != last_status_) {
    using gf_ara::phm::CheckpointStatus;
    if (st == CheckpointStatus::kOk &&
        (last_status_ == CheckpointStatus::kAliveMissed ||
         last_status_ == CheckpointStatus::kDeadlineMissed ||
         last_status_ == CheckpointStatus::kLogicalFault)) {
      ++recover_count_;
      log.Info("phm", "t_ms=" + std::to_string(MonoMs()) +
                          " phm recovered entity=" + std::string(entity_->Name()));
    } else if (st == CheckpointStatus::kAliveMissed ||
               st == CheckpointStatus::kDeadlineMissed ||
               st == CheckpointStatus::kLogicalFault) {
      OnFault(st);
    }
    last_status_ = st;
  }
}

}  // namespace gf_ara::runtime
