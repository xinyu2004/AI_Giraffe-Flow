// P2.5 G3: iceoryx session inject — publish EgoMotion (etc.) from session JSONL.
// B1 boundary: do NOT start vehicle_can_gateway; inject replaces gateway EgoMotion.
// B2 module test: start only DUT apps + inject; GF_INJECT_SERVICES = DUT requires.
//
// Drive (GF_INJECT_MODE):
//   continuous (default) — wall-clock replay; does not wait for GMT
//   playhead             — listen GF_INJECT_PORT (default 8767); wait for GMT cmds
//
// Control protocol (TCP, one JSON object per line):
//   → {"cmd":"hello"} | {"cmd":"status"} | {"cmd":"seek","index":N}
//   → {"cmd":"step"} | {"cmd":"play","rate":1.0} | {"cmd":"pause"}
//   ← {"op":"hello","proto":"gf_inject_ctrl",...} | {"op":"status",...}
//   ← {"op":"published","index":N,"topic":"...","t_ns":...} | {"op":"error","msg":"..."}
//
// Event index == GMT session index (all non-tag_meta lines). Non-allowlisted
// topics are seekable but not published.
//
// Never run alongside a live publisher of the same service.

#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_gen/skeleton/ego_motion_skeleton.hpp"
#include "gf_gen/types/ego_motion.hpp"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <unistd.h>

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <set>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

namespace {

struct Event {
  std::uint64_t t_ns{0};
  std::string topic;
  std::string data_json;
};

enum class DriveMode { Continuous, Playhead };

DriveMode parse_drive_mode() {
  const char* env = std::getenv("GF_INJECT_MODE");
  std::string raw = env && *env ? env : "continuous";
  for (char& c : raw) {
    if (c >= 'A' && c <= 'Z') {
      c = static_cast<char>(c - 'A' + 'a');
    }
  }
  if (raw == "playhead" || raw == "controlled" || raw == "wait") {
    return DriveMode::Playhead;
  }
  return DriveMode::Continuous;
}

int parse_control_port() {
  const char* env = std::getenv("GF_INJECT_PORT");
  if (!env || !*env) {
    return 8767;
  }
  const int p = std::atoi(env);
  return p > 0 && p < 65536 ? p : 8767;
}

std::string parse_control_host() {
  const char* env = std::getenv("GF_INJECT_HOST");
  return env && *env ? std::string(env) : "0.0.0.0";
}

std::set<std::string> parse_allowlist() {
  const char* env = std::getenv("GF_INJECT_SERVICES");
  std::string raw = env && *env ? env : "EgoMotion";
  std::set<std::string> out;
  std::string cur;
  for (char c : raw) {
    if (c == ',' || c == ';' || c == ' ') {
      if (!cur.empty()) {
        const std::string pref = "services.semantic.";
        if (cur.rfind(pref, 0) == 0) {
          cur = cur.substr(pref.size());
        }
        out.insert(cur);
        cur.clear();
      }
    } else {
      cur.push_back(c);
    }
  }
  if (!cur.empty()) {
    const std::string pref = "services.semantic.";
    if (cur.rfind(pref, 0) == 0) {
      cur = cur.substr(pref.size());
    }
    out.insert(cur);
  }
  return out;
}

bool extract_u64(const std::string& s, const char* key, std::uint64_t* out) {
  const std::string pat = std::string("\"") + key + "\":";
  auto pos = s.find(pat);
  if (pos == std::string::npos) {
    return false;
  }
  pos += pat.size();
  while (pos < s.size() && (s[pos] == ' ')) {
    ++pos;
  }
  char* end = nullptr;
  unsigned long long v = std::strtoull(s.c_str() + pos, &end, 10);
  if (end == s.c_str() + pos) {
    return false;
  }
  *out = static_cast<std::uint64_t>(v);
  return true;
}

bool extract_f32(const std::string& s, const char* key, float* out) {
  const std::string pat = std::string("\"") + key + "\":";
  auto pos = s.find(pat);
  if (pos == std::string::npos) {
    return false;
  }
  pos += pat.size();
  while (pos < s.size() && (s[pos] == ' ')) {
    ++pos;
  }
  char* end = nullptr;
  double v = std::strtod(s.c_str() + pos, &end);
  if (end == s.c_str() + pos) {
    return false;
  }
  *out = static_cast<float>(v);
  return true;
}

bool extract_u8(const std::string& s, const char* key, std::uint8_t* out) {
  std::uint64_t v = 0;
  if (!extract_u64(s, key, &v)) {
    return false;
  }
  *out = static_cast<std::uint8_t>(v);
  return true;
}

bool extract_f64_field(const std::string& s, const char* key, double* out) {
  const std::string pat = std::string("\"") + key + "\":";
  auto pos = s.find(pat);
  if (pos == std::string::npos) {
    return false;
  }
  pos += pat.size();
  while (pos < s.size() && (s[pos] == ' ')) {
    ++pos;
  }
  char* end = nullptr;
  double v = std::strtod(s.c_str() + pos, &end);
  if (end == s.c_str() + pos) {
    return false;
  }
  *out = v;
  return true;
}

std::string extract_string_field(const std::string& line, const char* key) {
  const std::string pat = std::string("\"") + key + "\":";
  auto pos = line.find(pat);
  if (pos == std::string::npos) {
    return {};
  }
  pos += pat.size();
  while (pos < line.size() && (line[pos] == ' ' || line[pos] == '\t')) {
    ++pos;
  }
  if (pos >= line.size() || line[pos] != '"') {
    return {};
  }
  ++pos;
  auto end = line.find('"', pos);
  if (end == std::string::npos) {
    return {};
  }
  return line.substr(pos, end - pos);
}

std::string extract_object_field(const std::string& line, const char* key) {
  const std::string pat = std::string("\"") + key + "\":{";
  auto pos = line.find(pat);
  if (pos == std::string::npos) {
    return {};
  }
  pos += pat.size() - 1;  // on '{'
  int depth = 0;
  for (size_t i = pos; i < line.size(); ++i) {
    if (line[i] == '{') {
      ++depth;
    } else if (line[i] == '}') {
      --depth;
      if (depth == 0) {
        return line.substr(pos, i - pos + 1);
      }
    }
  }
  return {};
}

std::vector<Event> load_session(const std::string& path) {
  std::ifstream in(path);
  std::vector<Event> events;
  if (!in) {
    std::cerr << "gf-iox-obs-inject: cannot open " << path << "\n";
    return events;
  }
  std::string line;
  while (std::getline(in, line)) {
    if (line.empty()) {
      continue;
    }
    if (line.find("\"type\":\"tag_meta\"") != std::string::npos) {
      continue;
    }
    Event e;
    if (!extract_u64(line, "t_ns", &e.t_ns)) {
      extract_u64(line, "log_time_ns", &e.t_ns);
    }
    e.topic = extract_string_field(line, "topic");
    e.data_json = extract_object_field(line, "data");
    if (e.topic.empty()) {
      continue;
    }
    events.push_back(std::move(e));
  }
  return events;
}

bool topic_is(const std::string& topic, const char* short_name) {
  if (topic == short_name) {
    return true;
  }
  const std::string a = std::string("/gf/") + short_name;
  if (topic == a) {
    return true;
  }
  const std::size_t n = std::strlen(short_name);
  return topic.size() >= n && topic.compare(topic.size() - n, n, short_name) == 0;
}

bool topic_allowed(const Event& e, const std::set<std::string>& allow) {
  for (const auto& s : allow) {
    if (topic_is(e.topic, s.c_str())) {
      return true;
    }
  }
  return false;
}

gf_gen::EgoMotion parse_ego(const Event& e) {
  gf_gen::EgoMotion ego{};
  ego.timestamp_ns = e.t_ns;
  extract_u64(e.data_json, "timestamp_ns", &ego.timestamp_ns);
  extract_f32(e.data_json, "speed_mps", &ego.speed_mps);
  extract_f32(e.data_json, "yaw_rate_degps", &ego.yaw_rate_degps);
  extract_f32(e.data_json, "steer_angle_deg", &ego.steer_angle_deg);
  extract_u8(e.data_json, "gear", &ego.gear);
  return ego;
}

bool publish_event(gf_gen::EgoMotionSkeleton& ego_pub,
                   const Event& e,
                   const std::set<std::string>& allow,
                   bool want_ego) {
  if (!topic_allowed(e, allow)) {
    return false;
  }
  if (want_ego && topic_is(e.topic, "EgoMotion")) {
    auto ego = parse_ego(e);
    (void)ego_pub.Send(ego);
    return true;
  }
  return false;
}

void send_line(int fd, const std::string& line) {
  const std::string msg = line + "\n";
  (void)::send(fd, msg.data(), msg.size(), MSG_NOSIGNAL);
}

std::string json_escape(const std::string& s) {
  std::string o;
  o.reserve(s.size() + 8);
  for (char c : s) {
    if (c == '\\' || c == '"') {
      o.push_back('\\');
    }
    o.push_back(c);
  }
  return o;
}

int listen_control(const std::string& host, int port) {
  const int fd = ::socket(AF_INET, SOCK_STREAM, 0);
  if (fd < 0) {
    return -1;
  }
  int yes = 1;
  (void)::setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
  sockaddr_in addr{};
  addr.sin_family = AF_INET;
  addr.sin_port = htons(static_cast<uint16_t>(port));
  if (::inet_pton(AF_INET, host.c_str(), &addr.sin_addr) != 1) {
    // fallback any
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
  }
  if (::bind(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0) {
    ::close(fd);
    return -1;
  }
  if (::listen(fd, 1) < 0) {
    ::close(fd);
    return -1;
  }
  return fd;
}

int run_continuous(const std::vector<Event>& events,
                   const std::set<std::string>& allow,
                   bool want_ego,
                   gf_gen::EgoMotionSkeleton& ego_pub) {
  const std::uint64_t t0 = events.front().t_ns;
  const auto wall0 = std::chrono::steady_clock::now();
  std::size_t sent = 0;

  for (const auto& e : events) {
    if (iox::posix::hasTerminationRequested()) {
      break;
    }
    if (!topic_allowed(e, allow)) {
      continue;
    }
    const auto target =
        wall0 + std::chrono::nanoseconds(e.t_ns > t0 ? e.t_ns - t0 : 0);
    std::this_thread::sleep_until(target);
    if (publish_event(ego_pub, e, allow, want_ego)) {
      ++sent;
    }
  }

  std::cerr << "gf-iox-obs-inject: continuous done sent=" << sent << "\n";
  for (int i = 0; i < 50 && !iox::posix::hasTerminationRequested(); ++i) {
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
  }
  return 0;
}

int run_playhead(const std::vector<Event>& events,
                 const std::set<std::string>& allow,
                 bool want_ego,
                 gf_gen::EgoMotionSkeleton& ego_pub,
                 const std::string& host,
                 int port) {
  const int listen_fd = listen_control(host, port);
  if (listen_fd < 0) {
    std::cerr << "gf-iox-obs-inject: cannot bind " << host << ":" << port << "\n";
    return EXIT_FAILURE;
  }
  std::cerr << "gf-iox-obs-inject: playhead LISTENING on tcp://" << host << ":" << port
            << " events=" << events.size()
            << " — waiting for GMT inject ctrl CONNECT\n";

  int client_fd = -1;
  std::string inbuf;
  int index = -1;  // last published / current playhead
  bool playing = false;
  double rate = 1.0;
  auto next_deadline = std::chrono::steady_clock::now();
  std::size_t sent = 0;

  auto emit_status = [&](int fd) {
    if (fd < 0) {
      return;
    }
    std::ostringstream oss;
    oss << "{\"op\":\"status\",\"index\":" << index << ",\"events\":" << events.size()
        << ",\"sent\":" << sent << ",\"state\":\"" << (playing ? "playing" : "paused")
        << "\",\"rate\":" << rate << "}";
    send_line(fd, oss.str());
  };

  auto emit_hello = [&](int fd) {
    std::ostringstream oss;
    oss << "{\"op\":\"hello\",\"proto\":\"gf_inject_ctrl\",\"version\":1"
        << ",\"mode\":\"playhead\",\"events\":" << events.size()
        << ",\"index\":" << index << ",\"port\":" << port << "}";
    send_line(fd, oss.str());
  };

  auto do_publish_at = [&](int idx) -> bool {
    if (idx < 0 || static_cast<size_t>(idx) >= events.size()) {
      return false;
    }
    index = idx;
    const Event& e = events[static_cast<size_t>(idx)];
    const bool ok = publish_event(ego_pub, e, allow, want_ego);
    if (ok) {
      ++sent;
    }
    if (client_fd >= 0) {
      std::ostringstream oss;
      oss << "{\"op\":\"published\",\"index\":" << idx << ",\"topic\":\""
          << json_escape(e.topic) << "\",\"t_ns\":" << e.t_ns
          << ",\"injected\":" << (ok ? "true" : "false") << "}";
      send_line(client_fd, oss.str());
    }
    return ok;
  };

  auto handle_cmd = [&](const std::string& line) {
    if (line.find("\"cmd\"") == std::string::npos) {
      return;
    }
    const std::string cmd = extract_string_field(line, "cmd");
    if (cmd == "hello" || cmd == "status") {
      if (cmd == "hello") {
        emit_hello(client_fd);
      }
      emit_status(client_fd);
      return;
    }
    if (cmd == "pause") {
      playing = false;
      emit_status(client_fd);
      return;
    }
    if (cmd == "play") {
      double r = 1.0;
      extract_f64_field(line, "rate", &r);
      if (r <= 0.0) {
        r = 1.0;
      }
      rate = r;
      playing = true;
      if (index < 0) {
        (void)do_publish_at(0);
      }
      next_deadline = std::chrono::steady_clock::now();
      emit_status(client_fd);
      return;
    }
    if (cmd == "seek") {
      std::uint64_t idx_u = 0;
      if (!extract_u64(line, "index", &idx_u)) {
        send_line(client_fd, "{\"op\":\"error\",\"msg\":\"seek needs index\"}");
        return;
      }
      playing = false;
      const int idx = static_cast<int>(idx_u);
      if (idx < 0 || static_cast<size_t>(idx) >= events.size()) {
        send_line(client_fd, "{\"op\":\"error\",\"msg\":\"index out of range\"}");
        return;
      }
      (void)do_publish_at(idx);
      emit_status(client_fd);
      return;
    }
    if (cmd == "step") {
      playing = false;
      const int next = index < 0 ? 0 : index + 1;
      if (static_cast<size_t>(next) >= events.size()) {
        send_line(client_fd, "{\"op\":\"error\",\"msg\":\"at end\"}");
        emit_status(client_fd);
        return;
      }
      (void)do_publish_at(next);
      emit_status(client_fd);
      return;
    }
    send_line(client_fd,
              "{\"op\":\"error\",\"msg\":\"unknown cmd (hello|status|seek|step|play|pause)\"}");
  };

  while (!iox::posix::hasTerminationRequested()) {
    fd_set rfds;
    FD_ZERO(&rfds);
    FD_SET(listen_fd, &rfds);
    int maxfd = listen_fd;
    if (client_fd >= 0) {
      FD_SET(client_fd, &rfds);
      maxfd = std::max(maxfd, client_fd);
    }

    timeval tv{};
    tv.tv_sec = 0;
    tv.tv_usec = 20000;  // 20ms
    const int sel = ::select(maxfd + 1, &rfds, nullptr, nullptr, &tv);
    if (sel < 0) {
      break;
    }

    if (FD_ISSET(listen_fd, &rfds)) {
      sockaddr_in peer{};
      socklen_t plen = sizeof(peer);
      const int nfd = ::accept(listen_fd, reinterpret_cast<sockaddr*>(&peer), &plen);
      if (nfd >= 0) {
        if (client_fd >= 0) {
          ::close(client_fd);
        }
        client_fd = nfd;
        inbuf.clear();
        char ipbuf[INET_ADDRSTRLEN] = {};
        ::inet_ntop(AF_INET, &peer.sin_addr, ipbuf, sizeof(ipbuf));
        std::cerr << "gf-iox-obs-inject: GMT control CONNECTED from "
                  << ipbuf << ":" << ntohs(peer.sin_port)
                  << " (playhead ctrl ready)\n";
        emit_hello(client_fd);
        emit_status(client_fd);
      }
    }

    if (client_fd >= 0 && FD_ISSET(client_fd, &rfds)) {
      char buf[4096];
      const ssize_t n = ::recv(client_fd, buf, sizeof(buf), 0);
      if (n <= 0) {
        std::cerr << "gf-iox-obs-inject: GMT control DISCONNECTED "
                  << "(playhead idle, waiting for reconnect)\n";
        ::close(client_fd);
        client_fd = -1;
        playing = false;
        inbuf.clear();
      } else {
        inbuf.append(buf, static_cast<size_t>(n));
        for (;;) {
          const auto nl = inbuf.find('\n');
          if (nl == std::string::npos) {
            break;
          }
          std::string line = inbuf.substr(0, nl);
          inbuf.erase(0, nl + 1);
          while (!line.empty() && (line.back() == '\r')) {
            line.pop_back();
          }
          if (!line.empty()) {
            handle_cmd(line);
          }
        }
      }
    }

    // auto-play: advance by session Δt / rate
    if (playing && !events.empty()) {
      const auto now = std::chrono::steady_clock::now();
      if (now >= next_deadline) {
        const int next = index < 0 ? 0 : index + 1;
        if (static_cast<size_t>(next) >= events.size()) {
          playing = false;
          if (client_fd >= 0) {
            emit_status(client_fd);
          }
        } else {
          std::uint64_t dt = 0;
          if (index >= 0) {
            const auto a = events[static_cast<size_t>(index)].t_ns;
            const auto b = events[static_cast<size_t>(next)].t_ns;
            dt = b > a ? b - a : 0;
          }
          (void)do_publish_at(next);
          const double scale = rate > 0.0 ? rate : 1.0;
          const auto wait_ns = static_cast<std::uint64_t>(static_cast<double>(dt) / scale);
          next_deadline = now + std::chrono::nanoseconds(wait_ns);
        }
      }
    }
  }

  if (client_fd >= 0) {
    ::close(client_fd);
  }
  ::close(listen_fd);
  std::cerr << "gf-iox-obs-inject: playhead exit sent=" << sent << "\n";
  return 0;
}

}  // namespace

int main(int argc, char** argv) {
  const char* env_path = std::getenv("GF_INJECT_SESSION");
  std::string path = (argc > 1 && argv[1][0]) ? argv[1] : (env_path ? env_path : "");
  if (path.empty()) {
    std::cerr << "gf-iox-obs-inject: need session path argv[1] or GF_INJECT_SESSION\n";
    return EXIT_FAILURE;
  }

  const DriveMode mode = parse_drive_mode();
  const auto allow = parse_allowlist();
  const bool want_ego = allow.count("EgoMotion") > 0;
  for (const auto& s : allow) {
    if (s != "EgoMotion") {
      std::cerr << "gf-iox-obs-inject: ignore unsupported '" << s
                << "' (MVP: EgoMotion only)\n";
    }
  }
  if (!want_ego) {
    std::cerr << "gf-iox-obs-inject: nothing to inject\n";
    return EXIT_FAILURE;
  }

  auto events = load_session(path);
  if (events.empty()) {
    std::cerr << "gf-iox-obs-inject: no events in " << path << "\n";
    return EXIT_FAILURE;
  }

  gf_ara::com::binding::iceoryx::InitRuntime("gf-iox-obs-inject");
  gf_gen::EgoMotionSkeleton ego_pub{};

  std::cerr << "gf-iox-obs-inject: session=" << path << " events=" << events.size()
            << " mode=" << (mode == DriveMode::Playhead ? "playhead" : "continuous")
            << " (do not co-publish with gateway)\n";

  if (mode == DriveMode::Playhead) {
    return run_playhead(
        events, allow, want_ego, ego_pub, parse_control_host(), parse_control_port());
  }
  return run_continuous(events, allow, want_ego, ego_pub);
}
