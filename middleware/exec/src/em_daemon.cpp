#include "gf_ara/exec/em_daemon.hpp"

#include "gf/osal/process.hpp"

#include <sys/stat.h>

#include <chrono>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <regex>
#include <sstream>
#include <thread>
#include <unordered_map>
#include <unistd.h>  // mkdir

namespace gf_ara::exec {
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

bool FileExists(const std::string& path) {
  struct stat st {};
  return ::stat(path.c_str(), &st) == 0 && S_ISREG(st.st_mode);
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
    std::cerr << "em_daemon: " << err << "\n";
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

bool EmDaemon::Load(std::string_view platform_dir, std::string_view launch_yaml,
                    std::string_view build_dir, std::string_view log_dir) {
  EmDaemonConfig cfg;
  cfg.platform_dir = std::string(platform_dir);
  cfg.build_dir = std::string(build_dir);
  cfg.log_dir = std::string(log_dir);

  std::string exec_path = JoinPath(cfg.platform_dir, "exec.yaml");
  if (ReadFile(exec_path).empty()) {
    const auto alt = JoinPath(cfg.platform_dir, "platform/exec.yaml");
    if (!ReadFile(alt).empty()) {
      exec_path = alt;
    }
  }
  const std::string exec_text = ReadFile(exec_path);
  if (exec_text.empty()) {
    std::cerr << "em_daemon: cannot read exec.yaml under " << cfg.platform_dir << "\n";
    return false;
  }

  const std::string launch_text = ReadFile(std::string(launch_yaml));
  if (launch_text.empty()) {
    std::cerr << "em_daemon: cannot read launch yaml " << launch_yaml << "\n";
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
        std::regex tok_re(R"(\"([^\"]+)\"|([A-Za-z0-9_./-]+))");
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
    std::cerr << "em_daemon: no processes to launch\n";
    return false;
  }
  return Configure(std::move(cfg));
}

bool EmDaemon::Spawn(Runtime& rt, bool is_relaunch) {
  const std::string bin = ResolveBinary(rt.spec, cfg_.build_dir);
  if (bin.empty() || !FileExists(bin)) {
    std::cerr << "em_daemon: binary missing for " << rt.spec.name << " path=" << bin << "\n";
    return false;
  }

  gf::osal::ProcessSpawnRequest req;
  req.executable = bin;
  req.args = rt.spec.args;
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
  if (is_relaunch) {
    req.env_set.emplace_back("GF_PHM_FAULT_MS", "0");
    req.env_set.emplace_back("GF_EM_RELAUNCH", "1");
  }

  const auto pid = gf::osal::SpawnProcess(req);
  if (!gf::osal::IsValidProcessId(pid)) {
    std::cerr << "em_daemon: SpawnProcess failed for " << rt.spec.name << "\n";
    return false;
  }

  rt.pid = pid;
  ++rt.launches;
  if (is_relaunch) {
    ++rt.restarts;
  }
  rt.ever_started = true;
  rt.terminal_exit = false;
  std::cout << "em_daemon: spawned name=" << rt.spec.name << " pid=" << pid
            << " relaunch=" << (is_relaunch ? "yes" : "no")
            << " launches=" << rt.launches << std::endl;
  return true;
}

bool EmDaemon::StartAll() {
  if (!cfg_.log_dir.empty()) {
    ::mkdir(cfg_.log_dir.c_str(), 0755);
  }
  for (auto& rt : runtimes_) {
    if (!Spawn(rt, false)) {
      return false;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(200));
  }
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
    std::cout << "em_daemon: child exit name=" << rt.spec.name << " pid=" << rt.pid
              << " code=" << exit_code << " signaled=" << (signaled ? "yes" : "no")
              << std::endl;
    rt.pid = gf::osal::kInvalidProcessId;

    const bool do_restart =
        !shutting_down_ && rt.spec.restart_enabled &&
        rt.restarts < rt.spec.max_restarts &&
        (exit_code == kEmRestartExitCode || signaled);

    if (do_restart) {
      std::cout << "em_daemon: relaunch name=" << rt.spec.name << " restart#"
                << (rt.restarts + 1) << std::endl;
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
        std::cerr << "em_daemon: deadline reached\n";
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
  std::this_thread::sleep_for(std::chrono::milliseconds(200));
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
