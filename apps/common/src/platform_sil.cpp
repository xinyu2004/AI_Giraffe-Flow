#include "gf_demo/platform_sil.hpp"

#include <cstdlib>
#include <fstream>
#include <iostream>
#include <regex>
#include <sstream>

namespace gf::demo::platform_sil {
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
  // Script uses GF_PHM_FAULT_MS; docs also mention GF_PHM_FAULT_INJECT_MS
  if (const char* a = std::getenv("GF_PHM_FAULT_MS"); a && *a) {
    return EnvU32("GF_PHM_FAULT_MS", 0);
  }
  return EnvU32("GF_PHM_FAULT_INJECT_MS", 0);
}

}  // namespace

std::string PlatformDir() {
  if (const char* d = std::getenv("GF_PLATFORM_DIR"); d && *d) {
    std::string out{d};
    while (!out.empty() && out.back() == '/') {
      out.pop_back();
    }
    // accept project root that contains platform/
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
    return cfg;
  }
  const std::string text = ReadFile(dir + "/exec.yaml");
  if (text.empty()) {
    std::cerr << "platform_sil: cannot read " << dir << "/exec.yaml\n";
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
    std::cerr << "platform_sil: cannot read " << dir << "/phm.yaml\n";
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
  // last id: before this process line
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
  return cfg;
}

bool ProcessSupervisor::Start(std::string_view process_name) {
  process_ = std::string(process_name);
  const auto exec_cfg = LoadExecProcess(process_name);
  if (PlatformDir().empty()) {
    std::cerr << "platform_sil: GF_PLATFORM_DIR unset — using Offer defaults for "
              << process_ << "\n";
  } else if (!exec_cfg.found) {
    std::cerr << "platform_sil: process not in exec.yaml: " << process_ << "\n";
    return false;
  } else if (!exec_cfg.execution_client) {
    std::cerr << "platform_sil: execution_client=false for " << process_ << "\n";
    return false;
  }

  using gf_ara::exec::ExecutionClient;
  using gf_ara::exec::ExecutionState;
  if (!ExecutionClient::Offer(process_)) {
    std::cerr << "platform_sil: Offer failed for " << process_ << "\n";
    return false;
  }
  if (!ExecutionClient::ReportExecutionState(ExecutionState::kRunning)) {
    std::cerr << "platform_sil: Report Running failed for " << process_ << "\n";
    return false;
  }
  // Stable assert token for smoke scripts
  std::cout << "Offer→Running process=" << process_;
  if (!exec_cfg.function_group.empty()) {
    std::cout << " fg=" << exec_cfg.function_group;
  }
  std::cout << std::endl;

  const auto phm_cfg = LoadPhmEntity(process_name);
  if (phm_cfg.found) {
    entity_.emplace(phm_cfg.id);
    alive_period_ms_ = phm_cfg.alive_period_ms;
    entity_->Configure(phm_cfg.alive_period_ms, phm_cfg.alive_timeout_ms);
    next_alive_ = std::chrono::steady_clock::now();
    std::cout << "phm entity=" << phm_cfg.id << " period_ms=" << phm_cfg.alive_period_ms
              << " timeout_ms=" << phm_cfg.alive_timeout_ms << std::endl;

    const auto fault_ms = FaultMs();
    if (fault_ms > 0) {
      fault_pending_ = true;
      std::cout << "FAULT inject armed for " << fault_ms << " ms after first Alive\n";
    }
  } else if (!PlatformDir().empty()) {
    std::cout << "platform_sil: no phm entity for " << process_ << " (ok)\n";
  }
  return true;
}

void ProcessSupervisor::Tick() {
  if (!entity_) {
    return;
  }
  const auto now = std::chrono::steady_clock::now();

  if (fault_pending_ && ever_alive_) {
    const auto fault_ms = FaultMs();
    fault_until_ = now + std::chrono::milliseconds(fault_ms);
    fault_pending_ = false;
    fault_active_ = true;
    std::cout << "FAULT inject begin entity=" << entity_->Name() << std::endl;
  }

  if (fault_active_ && now >= fault_until_) {
    std::cout << "fault window ended entity=" << entity_->Name() << std::endl;
    fault_active_ = false;
  }

  if (!fault_active_ && now >= next_alive_) {
    entity_->ReportAlive();
    ever_alive_ = true;
    next_alive_ = now + std::chrono::milliseconds(alive_period_ms_);
  }

  const auto st = entity_->Evaluate();
  if (st != last_status_) {
    if (st == gf_ara::phm::CheckpointStatus::kOk &&
        (last_status_ == gf_ara::phm::CheckpointStatus::kAliveMissed ||
         last_status_ == gf_ara::phm::CheckpointStatus::kDeadlineMissed)) {
      ++recover_count_;
      std::cout << "phm recovered entity=" << entity_->Name() << std::endl;
    } else if (st == gf_ara::phm::CheckpointStatus::kAliveMissed) {
      ++miss_count_;
      std::cout << "AliveMissed entity=" << entity_->Name() << std::endl;
    } else if (st == gf_ara::phm::CheckpointStatus::kDeadlineMissed) {
      ++miss_count_;
      std::cout << "DeadlineMissed entity=" << entity_->Name() << std::endl;
    }
    last_status_ = st;
  }
}

}  // namespace gf::demo::platform_sil
