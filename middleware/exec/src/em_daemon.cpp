#include "gf_ara/exec/em_daemon.hpp"

#include "gf/osal/process.hpp"
#include "gf/osal/clock.hpp"

#include <gf_ara/log/logger.hpp>

#if defined(GF_HAS_DEPLOY_CONFIG) && GF_HAS_DEPLOY_CONFIG
#include <gf_gen/deploy_config.hpp>
#endif

#include <sys/stat.h>

#include <chrono>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <regex>
#include <sstream>
#include <thread>
#include <unordered_map>
#include <unistd.h>  // mkdir

namespace gf_ara::exec {
namespace {

std::uint64_t MonoMs() {
  return gf::osal::MonotonicNowNs() / 1000000ULL;
}

std::string ReadFile(const std::string& path) {
  std::ifstream in(path);
  if (!in) {
    return {};
  }
  std::ostringstream ss;
  ss << in.rdbuf();
  return ss.str();
}

bool FileExists(const std::string& path) {
  struct stat st {};
  return ::stat(path.c_str(), &st) == 0 && S_ISREG(st.st_mode);
}

/// Best-effort: kill leftover platform daemons + IPC before EM Spawns them.
/// Same contract as RouDi: reclaim lives in EM, not run_sil/bash.
void ReclaimStalePlatformDaemons(std::string_view build_dir, bool reclaim_roudi,
                                 bool reclaim_dlt, std::string_view dlt_binary) {
  if (!reclaim_roudi && !reclaim_dlt) {
    return;
  }
  auto& log = gf_ara::log::Logger::Instance();
  log.Info("em", std::string("reclaim stale platform daemons before spawn") +
                     (reclaim_dlt ? " dlt" : "") + (reclaim_roudi ? " roudi" : ""));
  // Compare system() so -Wunused-result is quiet; non-zero (nothing to kill) OK.
  const auto run_ignore = [](const char* cmd) -> void {
    if (std::system(cmd) != 0) {
      // ignore
    }
  };

  if (reclaim_dlt) {
    // Prefer SKU binary path; fall back to basename match for in-tree builds.
    std::string dlt_path(dlt_binary);
    if (!dlt_path.empty() && dlt_path.front() != '/') {
      dlt_path = std::string(build_dir) + "/" + dlt_path;
    }
    if (!dlt_path.empty() && FileExists(dlt_path)) {
      const std::string cmd = "pkill -f '^" + dlt_path + "( |$)' >/dev/null 2>&1 || true";
      run_ignore(cmd.c_str());
    } else {
      run_ignore("pkill -x dlt-daemon >/dev/null 2>&1 || true");
    }
    // Stale FIFO makes libdlt block ~10s on register; remove with daemon.
    run_ignore("rm -f /tmp/dlt /tmp/dlt-ctrl.sock >/dev/null 2>&1 || true");
  }

  if (reclaim_roudi) {
    const std::string sku_roudi = std::string(build_dir) + "/iox-roudi";
    if (FileExists(sku_roudi)) {
      const std::string cmd = "pkill -f '^" + sku_roudi + "( |$)' >/dev/null 2>&1 || true";
      run_ignore(cmd.c_str());
    } else {
      run_ignore("pkill -x iox-roudi >/dev/null 2>&1 || true");
    }
    run_ignore("rm -f /dev/shm/iceoryx_* >/dev/null 2>&1 || true");
  }

  std::this_thread::sleep_for(std::chrono::milliseconds(300));
}

std::string JoinPath(std::string_view a, std::string_view b) {
  if (!b.empty() && b.front() == '/') {
    return std::string(b);
  }
  std::string out(a);
  while (!out.empty() && out.back() == '/') {
    out.pop_back();
  }
  out.push_back('/');
  out.append(b);
  return out;
}

std::vector<std::string> ParseDependsOn(const std::string& body) {
  std::vector<std::string> deps;
  const auto pos = body.find("depends_on:");
  if (pos == std::string::npos) {
    return deps;
  }
  const std::string after = body.substr(pos + std::strlen("depends_on:"));
  // Inline: depends_on: []  or depends_on: [a, b]
  std::smatch m;
  if (std::regex_search(after, m, std::regex(R"(^\s*\[([^\]]*)\])"))) {
    std::string inner = m[1].str();
    std::regex tok_re(R"(([A-Za-z0-9_./]+))");
    for (std::sregex_iterator it(inner.begin(), inner.end(), tok_re), end; it != end; ++it) {
      deps.push_back((*it)[1].str());
    }
    return deps;
  }
  // YAML list lines under depends_on
  std::istringstream iss(after);
  std::string line;
  bool in_list = false;
  while (std::getline(iss, line)) {
    if (!in_list) {
      if (line.find_first_not_of(" \t\r") == std::string::npos) {
        continue;
      }
      in_list = true;
    }
    std::smatch lm;
    if (std::regex_match(line, lm, std::regex(R"(^\s+-\s+(\S+)\s*$)"))) {
      deps.push_back(lm[1].str());
      continue;
    }
    // next key at process indent
    if (std::regex_match(line, std::regex(R"(^\s{0,4}[a-z_]+:.*)"))) {
      break;
    }
    if (!line.empty() && line[0] != ' ' && line[0] != '\t' && line[0] != '-') {
      break;
    }
  }
  return deps;
}

}  // namespace

bool EmDaemon::TopoSort(std::vector<EmProcessSpec>& procs, std::string& err) {
  std::unordered_map<std::string, std::size_t> idx;
  for (std::size_t i = 0; i < procs.size(); ++i) {
    idx[procs[i].name] = i;
  }
  std::vector<int> indeg(procs.size(), 0);
  std::vector<std::vector<std::size_t>> adj(procs.size());
  for (std::size_t i = 0; i < procs.size(); ++i) {
    for (const auto& d : procs[i].depends_on) {
      auto it = idx.find(d);
      if (it == idx.end()) {
        err = "unknown depends_on: " + d + " for " + procs[i].name;
        return false;
      }
      adj[it->second].push_back(i);
      ++indeg[i];
    }
  }
  std::vector<std::size_t> q;
  for (std::size_t i = 0; i < indeg.size(); ++i) {
    if (indeg[i] == 0) {
      q.push_back(i);
    }
  }
  std::vector<EmProcessSpec> ordered;
  ordered.reserve(procs.size());
  for (std::size_t qi = 0; qi < q.size(); ++qi) {
    const auto u = q[qi];
    ordered.push_back(procs[u]);
    for (auto v : adj[u]) {
      if (--indeg[v] == 0) {
        q.push_back(v);
      }
    }
  }
  if (ordered.size() != procs.size()) {
    err = "dependency cycle in exec.yaml";
    return false;
  }
  procs.swap(ordered);
  return true;
}

std::string EmDaemon::ResolveBinary(const EmProcessSpec& spec, std::string_view build_dir) {
  if (spec.binary.empty()) {
    return {};
  }
  if (spec.binary.front() == '/') {
    return spec.binary;
  }
  return JoinPath(build_dir, spec.binary);
}

bool EmDaemon::Configure(EmDaemonConfig cfg) {
  std::string err;
  if (!TopoSort(cfg.processes, err)) {
    gf_ara::log::Logger::Instance().Error("em", "em_daemon: " + err);
    return false;
  }
  cfg_ = std::move(cfg);
  runtimes_.clear();
  runtimes_.reserve(cfg_.processes.size());
  for (const auto& p : cfg_.processes) {
    Runtime rt;
    rt.spec = p;  // copy — keep cfg_.processes for Config() queries
    runtimes_.push_back(std::move(rt));
  }
  shutting_down_ = false;
  return true;
}

bool EmDaemon::LoadFromDeployConfig(std::string_view platform_dir,
                                    std::string_view build_dir,
                                    std::string_view log_dir) {
#if defined(GF_HAS_DEPLOY_CONFIG) && GF_HAS_DEPLOY_CONFIG
  EmDaemonConfig cfg;
  cfg.platform_dir = std::string(platform_dir);
  cfg.build_dir = std::string(build_dir);
  cfg.log_dir = std::string(log_dir);
  if (!gf_gen::deploy::kEm) {
    gf_ara::log::Logger::Instance().Error(
        "em", "deploy_config: kEm=false — exec not in runtime_modules");
    return false;
  }
  cfg.processes.reserve(gf_gen::deploy::kEmLaunchCount);
  for (std::size_t i = 0; i < gf_gen::deploy::kEmLaunchCount; ++i) {
    const auto& e = gf_gen::deploy::kEmLaunch[i];
    EmProcessSpec spec;
    spec.name = e.name ? e.name : "";
    spec.binary = e.binary ? e.binary : "";
    for (std::size_t a = 0; a < e.argc; ++a) {
      if (e.args != nullptr && e.args[a] != nullptr) {
        spec.args.emplace_back(e.args[a]);
      }
    }
    for (std::size_t d = 0; d < e.ndeps; ++d) {
      if (e.depends_on != nullptr && e.depends_on[d] != nullptr) {
        spec.depends_on.emplace_back(e.depends_on[d]);
      }
    }
    spec.restart_enabled = e.restart_enabled;
    spec.max_restarts = e.max_restarts;
    if (!spec.name.empty() && !spec.binary.empty()) {
      cfg.processes.push_back(std::move(spec));
    }
  }
  if (cfg.processes.empty()) {
    gf_ara::log::Logger::Instance().Error("em", "deploy_config: empty kEmLaunch");
    return false;
  }
  gf_ara::log::Logger::Instance().Info(
      "em", "LoadFromDeployConfig ok processes=" +
                std::to_string(cfg.processes.size()) +
                " platform=" + cfg.platform_dir);
  return Configure(std::move(cfg));
#else
  (void)platform_dir;
  (void)build_dir;
  (void)log_dir;
  gf_ara::log::Logger::Instance().Error(
      "em", "LoadFromDeployConfig: not compiled with GF_HAS_DEPLOY_CONFIG "
            "(SKU compose → generated/include/gf_gen/deploy_config.hpp)");
  return false;
#endif
}

bool EmDaemon::Load(std::string_view platform_dir, std::string_view launch_yaml,
                    std::string_view build_dir, std::string_view log_dir) {
  EmDaemonConfig cfg;
  cfg.platform_dir = std::string(platform_dir);
  cfg.build_dir = std::string(build_dir);
  cfg.log_dir = std::string(log_dir);

  // Product SIL: compose may freeze exec into generated/exec.yaml (GF_EM_EXEC).
  std::string exec_path;
  if (const char* override = std::getenv("GF_EM_EXEC");
      override != nullptr && override[0] != '\0') {
    exec_path = override;
  } else {
    exec_path = JoinPath(cfg.platform_dir, "exec.yaml");
    if (ReadFile(exec_path).empty()) {
      const auto alt = JoinPath(cfg.platform_dir, "platform/exec.yaml");
      if (!ReadFile(alt).empty()) {
        exec_path = alt;
      }
    }
  }
  const std::string exec_text = ReadFile(exec_path);
  if (exec_text.empty()) {
    gf_ara::log::Logger::Instance().Error(
        "em", "cannot read exec.yaml under " + cfg.platform_dir);
    return false;
  }

  const std::string launch_text = ReadFile(std::string(launch_yaml));
  if (launch_text.empty()) {
    gf_ara::log::Logger::Instance().Error(
        "em", "cannot read launch yaml " + std::string(launch_yaml));
    return false;
  }

  std::string phm_path = JoinPath(cfg.platform_dir, "phm.yaml");
  if (ReadFile(phm_path).empty()) {
    const auto alt = JoinPath(cfg.platform_dir, "platform/phm.yaml");
    if (!ReadFile(alt).empty()) {
      phm_path = alt;
    }
  }
  const std::string phm_text = ReadFile(phm_path);

  // Line-oriented parse (reliable under C++ ECMAScript regex).
  std::unordered_map<std::string, EmProcessSpec> launch_map;
  {
    EmProcessSpec cur;
    auto flush = [&]() {
      if (!cur.name.empty() && !cur.binary.empty()) {
        launch_map[cur.name] = cur;
      }
      cur = EmProcessSpec{};
    };
    std::istringstream iss(launch_text);
    std::string line;
    while (std::getline(iss, line)) {
      std::smatch m;
      if (std::regex_match(line, m, std::regex(R"(\s*- name:\s*(\S+)\s*)"))) {
        flush();
        cur.name = m[1].str();
        continue;
      }
      if (cur.name.empty()) {
        continue;
      }
      if (std::regex_match(line, m, std::regex(R"(\s*binary:\s*(\S+)\s*)"))) {
        cur.binary = m[1].str();
      } else if (std::regex_match(line, m, std::regex(R"(\s*max_restarts:\s*(\d+)\s*)"))) {
        cur.max_restarts = static_cast<std::uint32_t>(std::stoul(m[1].str()));
      } else if (std::regex_search(line, m, std::regex(R"(args:\s*\[([^\]]*)\])"))) {
        std::string args = m[1].str();
        // Allow $VAR tokens (compose freezes $GF_IOX_TOML / $GF_BUILD_DIR).
        std::regex tok_re(R"(\"([^\"]+)\"|([A-Za-z0-9_./$+-]+))");
        for (std::sregex_iterator at(args.begin(), args.end(), tok_re), aend; at != aend;
             ++at) {
          const std::string tok = (*at)[1].matched ? (*at)[1].str() : (*at)[2].str();
          if (!tok.empty()) {
            cur.args.push_back(tok);
          }
        }
      }
    }
    flush();
  }

  {
    EmProcessSpec cur;
    bool in_depends = false;
    auto flush = [&]() {
      if (cur.name.empty()) {
        return;
      }
      auto lit = launch_map.find(cur.name);
      if (lit == launch_map.end()) {
        cur = EmProcessSpec{};
        in_depends = false;
        return;
      }
      EmProcessSpec spec = lit->second;
      spec.name = cur.name;
      spec.depends_on = cur.depends_on;
      cfg.processes.push_back(std::move(spec));
      cur = EmProcessSpec{};
      in_depends = false;
    };
    std::istringstream iss(exec_text);
    std::string line;
    while (std::getline(iss, line)) {
      std::smatch m;
      if (std::regex_match(line, m, std::regex(R"(\s*- name:\s*(\S+)\s*)"))) {
        flush();
        cur.name = m[1].str();
        continue;
      }
      if (cur.name.empty()) {
        continue;
      }
      if (std::regex_match(line, std::regex(R"(\s*depends_on:\s*\[\s*\]\s*)"))) {
        in_depends = false;
        continue;
      }
      // Inline: depends_on: [a, b]
      if (std::regex_search(line, m, std::regex(R"(depends_on:\s*\[([^\]]*)\])"))) {
        in_depends = false;
        std::string inner = m[1].str();
        std::regex tok_re(R"(([A-Za-z0-9_./]+))");
        for (std::sregex_iterator it(inner.begin(), inner.end(), tok_re), end; it != end;
             ++it) {
          cur.depends_on.push_back((*it)[1].str());
        }
        continue;
      }
      if (std::regex_match(line, std::regex(R"(\s*depends_on:\s*)"))) {
        in_depends = true;
        continue;
      }
      if (in_depends && std::regex_match(line, m, std::regex(R"(\s*-\s+(\S+)\s*)"))) {
        cur.depends_on.push_back(m[1].str());
        continue;
      }
      if (std::regex_match(line, std::regex(R"(\s*[a-z_]+:.*)"))) {
        in_depends = false;
      }
    }
    flush();
  }

  if (cfg.processes.empty()) {
    for (auto& kv : launch_map) {
      cfg.processes.push_back(kv.second);
    }
  }

  if (!phm_text.empty()) {
    std::string cur_proc;
    std::istringstream piss(phm_text);
    std::string pline;
    while (std::getline(piss, pline)) {
      std::smatch m;
      if (std::regex_search(pline, m, std::regex(R"(process:\s*(\S+))"))) {
        cur_proc = m[1].str();
        continue;
      }
      if (!cur_proc.empty() &&
          std::regex_search(pline, m, std::regex(R"(on_failure:\s*(\S+))")) &&
          m[1].str() == "restart") {
        for (auto& p : cfg.processes) {
          if (p.name == cur_proc) {
            p.restart_enabled = true;
          }
        }
      }
    }
  }

  if (cfg.processes.empty()) {
    gf_ara::log::Logger::Instance().Error("em", "no processes to launch");
    return false;
  }
  gf_ara::log::Logger::Instance().Info(
      "em", "Load ok processes=" + std::to_string(cfg.processes.size()) +
                " platform=" + cfg.platform_dir);
  return Configure(std::move(cfg));
}

bool EmDaemon::Spawn(Runtime& rt, bool is_relaunch) {
  auto& log = gf_ara::log::Logger::Instance();
  const std::string bin = ResolveBinary(rt.spec, cfg_.build_dir);
  if (bin.empty() || !FileExists(bin)) {
    log.Error("em", "binary missing for " + rt.spec.name + " path=" + bin);
    return false;
  }

  auto ExpandArg = [&](std::string a) -> std::string {
    const auto replace_all = [](std::string s, const char* from, const char* to) {
      if (to == nullptr) {
        return s;
      }
      const std::string f(from);
      const std::string t(to);
      for (std::size_t p = 0; (p = s.find(f, p)) != std::string::npos; p += t.size()) {
        s.replace(p, f.size(), t);
      }
      return s;
    };
    a = replace_all(a, "$GF_BUILD_DIR", cfg_.build_dir.c_str());
    a = replace_all(a, "$GF_PLATFORM_DIR", cfg_.platform_dir.c_str());
    if (const char* iox = std::getenv("GF_IOX_TOML"); iox && *iox) {
      a = replace_all(a, "$GF_IOX_TOML", iox);
    }
    return a;
  };

  gf::osal::ProcessSpawnRequest req;
  req.executable = bin;
  req.args.clear();
  req.args.reserve(rt.spec.args.size());
  for (const auto& a : rt.spec.args) {
    req.args.push_back(ExpandArg(a));
  }
  if (!cfg_.log_dir.empty()) {
    std::string safe = rt.spec.name;
    for (char& c : safe) {
      if (c == '.') {
        c = '_';
      }
    }
    // Truncate only on first launch; append on relaunch so evidence keeps fault→restart.
    req.stdout_path = JoinPath(cfg_.log_dir, safe + ".log");
    req.stdout_append = is_relaunch;
  }
  req.env_set.emplace_back("GF_EM_MANAGED", "1");
  req.env_set.emplace_back("GF_PLATFORM_DIR", cfg_.platform_dir);
  // Children share the same structured log file as Host/EM (GMT Logging tab).
  if (const char* lf = std::getenv("GF_LOG_FILE"); lf != nullptr && lf[0] != '\0') {
    req.env_set.emplace_back("GF_LOG_FILE", lf);
  } else if (!cfg_.log_dir.empty()) {
    req.env_set.emplace_back("GF_LOG_FILE", JoinPath(cfg_.log_dir, "giraffe_modules.log"));
  }
  if (const char* ld = std::getenv("GF_LOG_DIR"); ld != nullptr && ld[0] != '\0') {
    req.env_set.emplace_back("GF_LOG_DIR", ld);
  } else if (!cfg_.log_dir.empty()) {
    req.env_set.emplace_back("GF_LOG_DIR", cfg_.log_dir);
  }
  if (is_relaunch) {
    req.env_set.emplace_back("GF_PHM_FAULT_MS", "0");
    req.env_set.emplace_back("GF_EM_RELAUNCH", "1");
  }

  const auto pid = gf::osal::SpawnProcess(req);
  if (!gf::osal::IsValidProcessId(pid)) {
    log.Error("em", "SpawnProcess failed for " + rt.spec.name);
    return false;
  }

  rt.pid = pid;
  ++rt.launches;
  if (is_relaunch) {
    ++rt.restarts;
  }
  rt.ever_started = true;
  rt.terminal_exit = false;
  // Keep "em_daemon: spawned" for SIL verify greps.
  log.Info("em", "t_ms=" + std::to_string(MonoMs()) + " em_daemon: spawned name=" +
                     rt.spec.name + " pid=" + std::to_string(pid) +
                     " relaunch=" + (is_relaunch ? "yes" : "no") +
                     " launches=" + std::to_string(rt.launches));
  return true;
}

bool EmDaemon::StartAll() {
  auto& log = gf_ara::log::Logger::Instance();
  if (!cfg_.log_dir.empty()) {
    ::mkdir(cfg_.log_dir.c_str(), 0755);
  }
  bool need_roudi = false;
  bool need_dlt = false;
  std::string dlt_binary;
  for (const auto& rt : runtimes_) {
    if (rt.spec.name.find("iox_roudi") != std::string::npos) {
      need_roudi = true;
    }
    if (rt.spec.name.find("dlt_daemon") != std::string::npos) {
      need_dlt = true;
      dlt_binary = rt.spec.binary;
    }
  }
  ReclaimStalePlatformDaemons(cfg_.build_dir, need_roudi, need_dlt, dlt_binary);
  log.Info("em", "StartAll begin count=" + std::to_string(runtimes_.size()));
  for (auto& rt : runtimes_) {
    if (!Spawn(rt, false)) {
      return false;
    }
    // Only real IPC daemons need a long beat; other host.* / apps stay short
    // (smoke host.base fixtures must not pay 600ms each).
    const bool ipc_daemon =
        rt.spec.name.find("iox_roudi") != std::string::npos ||
        rt.spec.name.find("dlt_daemon") != std::string::npos;
    std::this_thread::sleep_for(
        std::chrono::milliseconds(ipc_daemon ? 600 : 50));
  }
  log.Info("em", "StartAll done");
  return true;
}

bool EmDaemon::PollOnce() {
  if (shutting_down_) {
    return true;
  }
  for (auto& rt : runtimes_) {
    if (!gf::osal::IsValidProcessId(rt.pid)) {
      continue;
    }
    const auto wr = gf::osal::WaitProcess(rt.pid, true);
    if (wr.status == gf::osal::ProcessWaitStatus::kStillRunning) {
      continue;
    }
    if (wr.status == gf::osal::ProcessWaitStatus::kError) {
      continue;
    }

    const int exit_code =
        (wr.status == gf::osal::ProcessWaitStatus::kExited) ? wr.exit_code : -1;
    const bool signaled = (wr.status == gf::osal::ProcessWaitStatus::kSignaled);
    gf_ara::log::Logger::Instance().Info(
        "em", "t_ms=" + std::to_string(MonoMs()) + " em_daemon: child exit name=" +
                  rt.spec.name + " pid=" + std::to_string(rt.pid) +
                  " code=" + std::to_string(exit_code) +
                  " signaled=" + (signaled ? "yes" : "no"));
    rt.pid = gf::osal::kInvalidProcessId;

    const bool do_restart =
        !shutting_down_ && rt.spec.restart_enabled &&
        rt.restarts < rt.spec.max_restarts &&
        (exit_code == kEmRestartExitCode || signaled);

    if (do_restart) {
      gf_ara::log::Logger::Instance().Info(
          "em", "t_ms=" + std::to_string(MonoMs()) + " em_daemon: relaunch name=" +
                    rt.spec.name + " restart#" + std::to_string(rt.restarts + 1));
      if (!Spawn(rt, true)) {
        rt.terminal_exit = true;
        return false;
      }
    } else {
      rt.terminal_exit = true;
    }
  }
  return true;
}

int EmDaemon::RunForMs(std::uint32_t deadline_ms) {
  using clock = std::chrono::steady_clock;
  const auto t0 = clock::now();
  while (!shutting_down_) {
    if (!PollOnce()) {
      return 1;
    }
    bool all_done = true;
    for (const auto& rt : runtimes_) {
      if (!rt.terminal_exit) {
        all_done = false;
        break;
      }
    }
    if (all_done) {
      break;
    }

    if (deadline_ms > 0) {
      const auto ms =
          std::chrono::duration_cast<std::chrono::milliseconds>(clock::now() - t0).count();
      if (ms >= static_cast<long>(deadline_ms)) {
        gf_ara::log::Logger::Instance().Warn("em", "em_daemon: deadline reached");
        RequestShutdown();
        ShutdownAll();
        return 2;
      }
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
  }
  return 0;
}

void EmDaemon::RequestShutdown() {
  shutting_down_ = true;
}

void EmDaemon::ShutdownAll() {
  shutting_down_ = true;
  for (auto& rt : runtimes_) {
    if (gf::osal::IsValidProcessId(rt.pid)) {
      (void)gf::osal::TerminateProcess(rt.pid);
    }
  }
  std::this_thread::sleep_for(std::chrono::milliseconds(50));
  for (auto& rt : runtimes_) {
    if (gf::osal::IsValidProcessId(rt.pid)) {
      (void)gf::osal::KillProcess(rt.pid);
      (void)gf::osal::WaitProcess(rt.pid, false);
      rt.pid = gf::osal::kInvalidProcessId;
      rt.terminal_exit = true;
    }
  }
}

std::uint32_t EmDaemon::LaunchCount(std::string_view name) const noexcept {
  for (const auto& rt : runtimes_) {
    if (rt.spec.name == name) {
      return rt.launches;
    }
  }
  return 0;
}

std::uint32_t EmDaemon::RestartCount(std::string_view name) const noexcept {
  for (const auto& rt : runtimes_) {
    if (rt.spec.name == name) {
      return rt.restarts;
    }
  }
  return 0;
}

bool EmDaemon::IsRunning(std::string_view name) const noexcept {
  for (const auto& rt : runtimes_) {
    if (rt.spec.name == name) {
      return gf::osal::IsValidProcessId(rt.pid);
    }
  }
  return false;
}

}  // namespace gf_ara::exec
