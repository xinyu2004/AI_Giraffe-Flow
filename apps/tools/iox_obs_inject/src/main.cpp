// P2.5 G3: iceoryx session inject — publish EgoMotion (etc.) from session JSONL.
// B1 boundary: do NOT start vehicle_can_gateway; inject replaces gateway EgoMotion.
// B2 module test: start only DUT apps + inject; GF_INJECT_SERVICES = DUT requires.
//
// Drive (GF_INJECT_MODE):
//   continuous (default) — wall-clock replay from board session file (filtered + max)
//   playhead             — listen GF_INJECT_PORT (default 8767); GMT streams A/B windows
//
// Playhead = stream_window (default): session file optional; GMT holds the full session
// and pushes window_begin/push/window_end (or inject for scrub). Board keeps 2×256 events.
//
// Control protocol (TCP, one JSON object per line):
//   → {"cmd":"hello"} | {"cmd":"status"} | {"cmd":"seek","index":N}
//   → {"cmd":"step"} | {"cmd":"play","rate":1.0} | {"cmd":"pause"} | {"cmd":"reset"}
//   → {"cmd":"session","events":N}
//   → {"cmd":"window_begin","slot":"A"|"B","base":N}
//   → {"cmd":"push","slot":"A"|"B","index":i,"t_ns":...,"topic":"...","data":{...}}
//   → {"cmd":"window_end","slot":"A"|"B"}
//   → {"cmd":"inject","index":i,"t_ns":...,"topic":"...","data":{...}}
//   ← {"op":"hello","proto":"gf_inject_ctrl","caps":["stream_window"],...}
//   ← {"op":"status",...} | {"op":"published",...} | {"op":"need_window",...}
//   ← {"op":"eof","index":N} | {"op":"error","msg":"..."}
//
// Never run alongside a live publisher of the same service.

#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_gen/skeleton/ego_motion_skeleton.hpp"
#include "gf_gen/types/ego_motion.hpp"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <arpa/inet.h>
#include <fcntl.h>
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

// listen=yellow, connected=green, disconnected=cyan, error=red
constexpr const char* kAnsiReset = "\033[0m";
constexpr const char* kAnsiListen = "\033[33m";
constexpr const char* kAnsiOk = "\033[32m";
constexpr const char* kAnsiBye = "\033[36m";
constexpr const char* kAnsiErr = "\033[31m";

constexpr std::size_t kWindowMaxEvents = 256;
constexpr int kWindowBuffers = 2;
constexpr std::size_t kNeedWindowCount = 64;
constexpr std::size_t kDefaultMaxEvents = 20000;

bool want_color() {
  // stderr may be a fifo (run_sil tee); still color if a controlling tty exists.
  static int cached = -1;
  if (cached < 0) {
    const char* no = std::getenv("NO_COLOR");
    if (no && *no) {
      cached = 0;
    } else {
      const char* force = std::getenv("GF_STATUS_COLOR");
      if (!force || !*force) {
        force = std::getenv("FORCE_COLOR");
      }
      if (force && *force && force[0] != '0') {
        cached = 1;
      } else if (force && force[0] == '0') {
        cached = 0;
      } else if (::isatty(STDERR_FILENO)) {
        cached = 1;
      } else {
        const int tty = ::open("/dev/tty", O_WRONLY);
        if (tty >= 0) {
          cached = ::isatty(tty) ? 1 : 0;
          ::close(tty);
        } else {
          cached = 0;
        }
      }
    }
  }
  return cached != 0;
}

void inject_status(const char* color, const std::string& msg) {
  if (want_color()) {
    std::cerr << color << "[GMT Inject] " << msg << kAnsiReset << "\n";
  } else {
    std::cerr << "[GMT Inject] " << msg << "\n";
  }
  std::cerr.flush();
}

bool want_frame_trace() {
  const char* env = std::getenv("GF_INJECT_TRACE");
  return env && std::strcmp(env, "frame") == 0;
}

struct Event {
  std::uint64_t t_ns{0};
  std::string topic;
  std::string data_json;
};

struct StreamEvent {
  std::int64_t index{-1};
  std::uint64_t t_ns{0};
  std::string topic;
  std::string data_json;
};

struct Window {
  std::vector<StreamEvent> events;
  std::int64_t base{-1};
  bool ready{false};
  std::size_t cursor{0};

  void clear() {
    events.clear();
    base = -1;
    ready = false;
    cursor = 0;
  }
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

std::size_t parse_max_events() {
  const char* env = std::getenv("GF_INJECT_MAX_EVENTS");
  if (!env || !*env) {
    return kDefaultMaxEvents;
  }
  const long v = std::atol(env);
  return v > 0 ? static_cast<std::size_t>(v) : kDefaultMaxEvents;
}

bool parse_loop() {
  const char* env = std::getenv("GF_INJECT_LOOP");
  return env && env[0] == '1';
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

bool extract_i64(const std::string& s, const char* key, std::int64_t* out) {
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
  long long v = std::strtoll(s.c_str() + pos, &end, 10);
  if (end == s.c_str() + pos) {
    return false;
  }
  *out = static_cast<std::int64_t>(v);
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

bool topic_allowed(const std::string& topic, const std::set<std::string>& allow) {
  for (const auto& s : allow) {
    if (topic_is(topic, s.c_str())) {
      return true;
    }
  }
  return false;
}

bool topic_allowed(const Event& e, const std::set<std::string>& allow) {
  return topic_allowed(e.topic, allow);
}

// Continuous: load only allowlisted topics; fail if count would exceed max_events.
std::vector<Event> load_session_filtered(const std::string& path,
                                         const std::set<std::string>& allow,
                                         std::size_t max_events,
                                         std::string* err) {
  std::ifstream in(path);
  std::vector<Event> events;
  if (!in) {
    if (err) {
      *err = std::string("cannot open ") + path;
    }
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
    if (e.topic.empty() || !topic_allowed(e, allow)) {
      continue;
    }
    if (events.size() >= max_events) {
      if (err) {
        *err = std::string("GF_INJECT_MAX_EVENTS=") + std::to_string(max_events)
               + " exceeded while loading allowlisted events from " + path
               + " (use playhead stream mode for longer sessions)";
      }
      events.clear();
      return events;
    }
    events.push_back(std::move(e));
  }
  return events;
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

Event to_event(const StreamEvent& se) {
  Event e;
  e.t_ns = se.t_ns;
  e.topic = se.topic;
  e.data_json = se.data_json;
  return e;
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

int slot_index(const std::string& slot) {
  if (slot == "A" || slot == "a") {
    return 0;
  }
  if (slot == "B" || slot == "b") {
    return 1;
  }
  return -1;
}

char slot_name(int s) {
  return s == 0 ? 'A' : 'B';
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
                   gf_gen::EgoMotionSkeleton& ego_pub,
                   bool loop) {
  if (events.empty()) {
    std::cerr << "gf-iox-obs-inject: continuous: no allowlisted events\n";
    return EXIT_FAILURE;
  }

  int lap = 0;
  do {
    if (lap > 0) {
      inject_status(kAnsiOk, std::string("LOOP ") + std::to_string(lap));
    }
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

    std::cerr << "gf-iox-obs-inject: continuous lap=" << lap << " sent=" << sent << "\n";
    ++lap;
  } while (loop && !iox::posix::hasTerminationRequested());

  for (int i = 0; i < 50 && !iox::posix::hasTerminationRequested(); ++i) {
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
  }
  return 0;
}

int run_playhead_stream(const std::set<std::string>& allow,
                        bool want_ego,
                        gf_gen::EgoMotionSkeleton& ego_pub,
                        const std::string& host,
                        int port) {
  const int listen_fd = listen_control(host, port);
  if (listen_fd < 0) {
    inject_status(kAnsiErr, std::string("cannot bind ") + host + ":" + std::to_string(port));
    return EXIT_FAILURE;
  }
  inject_status(kAnsiListen,
                std::string("LISTENING tcp://") + host + ":" + std::to_string(port)
                    + " mode=playhead caps=stream_window"
                    + " window_max_events=" + std::to_string(kWindowMaxEvents)
                    + " window_buffers=" + std::to_string(kWindowBuffers));

  Window windows[2];
  int active = 0;  // slot currently used for play
  int client_fd = -1;
  std::string inbuf;
  std::int64_t index = -1;  // last published / current playhead (session index)
  std::int64_t session_events = 0;  // GMT-declared total via session cmd
  bool playing = false;
  double rate = 1.0;
  auto next_deadline = std::chrono::steady_clock::now();
  std::size_t sent = 0;

  auto emit_status = [&](int fd) {
    if (fd < 0) {
      return;
    }
    std::ostringstream oss;
    oss << "{\"op\":\"status\",\"index\":" << index << ",\"events\":" << session_events
        << ",\"sent\":" << sent << ",\"state\":\"" << (playing ? "playing" : "paused")
        << "\",\"rate\":" << rate << ",\"active_slot\":\"" << slot_name(active) << "\"}";
    send_line(fd, oss.str());
  };

  auto emit_hello = [&](int fd) {
    std::ostringstream oss;
    oss << "{\"op\":\"hello\",\"proto\":\"gf_inject_ctrl\",\"version\":1"
        << ",\"caps\":[\"stream_window\"]"
        << ",\"window_max_events\":" << kWindowMaxEvents
        << ",\"window_buffers\":" << kWindowBuffers
        << ",\"mode\":\"playhead\",\"events\":" << session_events
        << ",\"index\":" << index << ",\"port\":" << port << "}";
    send_line(fd, oss.str());
  };

  auto emit_need_window = [&](std::int64_t from, int slot = -1) {
    // Quiet: user-facing load logs are only LOAD A|B on window_end
    if (client_fd < 0) {
      return;
    }
    std::ostringstream oss;
    oss << "{\"op\":\"need_window\",\"from\":" << from
        << ",\"count\":" << kNeedWindowCount;
    if (slot >= 0) {
      oss << ",\"slot\":\"" << slot_name(slot) << "\"";
    }
    oss << "}";
    send_line(client_fd, oss.str());
  };

  auto emit_published = [&](const StreamEvent& se, bool ok) {
    if (client_fd < 0) {
      return;
    }
    std::ostringstream oss;
    oss << "{\"op\":\"published\",\"index\":" << se.index << ",\"topic\":\""
        << json_escape(se.topic) << "\",\"t_ns\":" << se.t_ns
        << ",\"injected\":" << (ok ? "true" : "false") << "}";
    send_line(client_fd, oss.str());
  };

  auto emit_eof = [&]() {
    if (client_fd < 0) {
      return;
    }
    std::ostringstream oss;
    oss << "{\"op\":\"eof\",\"index\":" << index << "}";
    send_line(client_fd, oss.str());
  };

  auto find_in_windows = [&](std::int64_t session_idx, int* slot_out,
                             std::size_t* cursor_out) -> bool {
    for (int s = 0; s < 2; ++s) {
      for (std::size_t i = 0; i < windows[s].events.size(); ++i) {
        if (windows[s].events[i].index == session_idx) {
          if (slot_out) {
            *slot_out = s;
          }
          if (cursor_out) {
            *cursor_out = i;
          }
          return true;
        }
      }
    }
    return false;
  };

  auto do_publish_stream = [&](const StreamEvent& se) -> bool {
    index = se.index;
    const Event e = to_event(se);
    const bool ok = publish_event(ego_pub, e, allow, want_ego);
    if (ok) {
      ++sent;
    }
    emit_published(se, ok);
    if (want_frame_trace()) {
      inject_status(kAnsiOk,
                    std::string("frame index=") + std::to_string(se.index)
                        + " topic=" + se.topic
                        + " injected=" + (ok ? "true" : "false"));
    }
    return ok;
  };

  auto invalidate_both = [&]() {
    windows[0].clear();
    windows[1].clear();
    active = 0;
  };

  auto log_reset_ab = [&]() {
    inject_status(kAnsiOk, "RESET A");
    inject_status(kAnsiOk, "RESET B");
  };

  auto parse_stream_fields = [&](const std::string& line, StreamEvent* se) -> bool {
    std::int64_t idx = -1;
    if (!extract_i64(line, "index", &idx)) {
      return false;
    }
    se->index = idx;
    if (!extract_u64(line, "t_ns", &se->t_ns)) {
      se->t_ns = 0;
    }
    se->topic = extract_string_field(line, "topic");
    se->data_json = extract_object_field(line, "data");
    return !se->topic.empty();
  };

  auto at_session_eof = [&]() -> bool {
    return session_events > 0 && index >= 0 && index >= session_events - 1;
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
    if (cmd == "reset") {
      playing = false;
      index = -1;
      invalidate_both();
      log_reset_ab();
      emit_status(client_fd);
      return;
    }
    if (cmd == "session") {
      std::int64_t n = 0;
      if (!extract_i64(line, "events", &n) || n < 0) {
        send_line(client_fd, "{\"op\":\"error\",\"msg\":\"session needs events>=0\"}");
        return;
      }
      session_events = n;
      inject_status(kAnsiListen,
                    std::string("SESSION from GMT events=") + std::to_string(n));
      emit_status(client_fd);
      return;
    }
    if (cmd == "window_begin") {
      const std::string slot = extract_string_field(line, "slot");
      const int s = slot_index(slot);
      std::int64_t base = 0;
      if (s < 0 || !extract_i64(line, "base", &base)) {
        send_line(client_fd,
                  "{\"op\":\"error\",\"msg\":\"window_begin needs slot A|B and base\"}");
        return;
      }
      windows[s].clear();
      windows[s].base = base;
      windows[s].ready = false;
      emit_status(client_fd);
      return;
    }
    if (cmd == "push") {
      const std::string slot = extract_string_field(line, "slot");
      const int s = slot_index(slot);
      if (s < 0) {
        send_line(client_fd, "{\"op\":\"error\",\"msg\":\"push needs slot A|B\"}");
        return;
      }
      if (windows[s].ready) {
        send_line(client_fd, "{\"op\":\"error\",\"msg\":\"push on ready window; window_begin first\"}");
        return;
      }
      if (windows[s].base < 0) {
        send_line(client_fd, "{\"op\":\"error\",\"msg\":\"window_begin first\"}");
        return;
      }
      if (windows[s].events.size() >= kWindowMaxEvents) {
        send_line(client_fd, "{\"op\":\"error\",\"msg\":\"window full\"}");
        return;
      }
      StreamEvent se;
      if (!parse_stream_fields(line, &se)) {
        send_line(client_fd, "{\"op\":\"error\",\"msg\":\"push needs index,topic,data\"}");
        return;
      }
      windows[s].events.push_back(std::move(se));
      return;
    }
    if (cmd == "window_end") {
      const std::string slot = extract_string_field(line, "slot");
      const int s = slot_index(slot);
      if (s < 0) {
        send_line(client_fd, "{\"op\":\"error\",\"msg\":\"window_end needs slot A|B\"}");
        return;
      }
      windows[s].ready = true;
      windows[s].cursor = 0;
      // One log per slot load (not per-frame inject scrub)
      inject_status(kAnsiOk,
                    std::string("LOAD ") + slot_name(s)
                        + " base=" + std::to_string(windows[s].base)
                        + " n=" + std::to_string(windows[s].events.size()));
      emit_status(client_fd);
      return;
    }
    if (cmd == "inject") {
      StreamEvent se;
      if (!parse_stream_fields(line, &se)) {
        send_line(client_fd, "{\"op\":\"error\",\"msg\":\"inject needs index,topic,data\"}");
        return;
      }
      playing = false;
      (void)do_publish_stream(se);
      // Per-frame scrub: quiet (use GF_INJECT_TRACE=frame for detail)
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
      next_deadline = std::chrono::steady_clock::now();

      // If no playhead yet, try publish first available in a ready window.
      if (index < 0) {
        bool started = false;
        for (int s = 0; s < 2; ++s) {
          if (windows[s].ready && !windows[s].events.empty()) {
            active = s;
            windows[s].cursor = 0;
            (void)do_publish_stream(windows[s].events[0]);
            started = true;
            break;
          }
        }
        if (!started) {
          playing = false;
          emit_need_window(0);
          send_line(client_fd, "{\"op\":\"error\",\"msg\":\"need_window\"}");
        }
      }
      emit_status(client_fd);
      return;
    }
    if (cmd == "seek") {
      std::int64_t idx = 0;
      if (!extract_i64(line, "index", &idx) || idx < 0) {
        send_line(client_fd, "{\"op\":\"error\",\"msg\":\"seek needs index\"}");
        return;
      }
      playing = false;
      index = idx;
      // Quiet scrub seeks — only LOAD A|B logs data arrival

      int found_slot = -1;
      std::size_t found_cur = 0;
      if (find_in_windows(idx, &found_slot, &found_cur)) {
        active = found_slot;
        windows[found_slot].cursor = found_cur;
        (void)do_publish_stream(windows[found_slot].events[found_cur]);
        emit_status(client_fd);
        return;
      }

      // Not in A/B — invalidate and ask GMT to refill (scrub uses inject primarily).
      invalidate_both();
      emit_need_window(idx);
      send_line(client_fd, "{\"op\":\"error\",\"msg\":\"need_window\"}");
      emit_status(client_fd);
      return;
    }
    if (cmd == "step") {
      playing = false;
      const std::int64_t next = index < 0 ? 0 : index + 1;
      if (session_events > 0 && next >= session_events) {
        send_line(client_fd, "{\"op\":\"error\",\"msg\":\"at end\"}");
        emit_status(client_fd);
        return;
      }
      int found_slot = -1;
      std::size_t found_cur = 0;
      if (find_in_windows(next, &found_slot, &found_cur)) {
        active = found_slot;
        windows[found_slot].cursor = found_cur;
        (void)do_publish_stream(windows[found_slot].events[found_cur]);
        if (at_session_eof()) {
          emit_eof();
        }
        emit_status(client_fd);
        return;
      }
      emit_need_window(next);
      send_line(client_fd, "{\"op\":\"error\",\"msg\":\"need_window\"}");
      emit_status(client_fd);
      return;
    }
    send_line(client_fd,
              "{\"op\":\"error\",\"msg\":\"unknown cmd "
              "(hello|status|seek|step|play|pause|reset|session|"
              "window_begin|push|window_end|inject)\"}");
  };

  auto try_advance_play = [&]() {
    if (!playing) {
      return;
    }
    const auto now = std::chrono::steady_clock::now();
    if (now < next_deadline) {
      return;
    }

    Window& cur = windows[active];
    // Need a ready window with content past current cursor.
    if (!cur.ready || cur.events.empty() || cur.cursor + 1 >= cur.events.size()) {
      const int other = 1 - active;
      if (windows[other].ready && !windows[other].events.empty()) {
        // Free the exhausted slot for GMT prefetch.
        cur.clear();
        active = other;
        windows[active].cursor = 0;
        // Prefetch hint for the freed slot.
        const std::int64_t prefetch_from =
            windows[active].events.back().index + 1;
        if (session_events <= 0 || prefetch_from < session_events) {
          emit_need_window(prefetch_from, 1 - active);
        }
        // Publish first of new active immediately.
        (void)do_publish_stream(windows[active].events[0]);
        next_deadline = now;
        if (at_session_eof()) {
          playing = false;
          emit_eof();
          emit_status(client_fd);
        }
        return;
      }
      playing = false;
      const std::int64_t from = index < 0 ? 0 : index + 1;
      emit_need_window(from, other);
      send_line(client_fd, "{\"op\":\"error\",\"msg\":\"need_window\"}");
      emit_status(client_fd);
      return;
    }

    const std::size_t next_cur = cur.cursor + 1;
    const StreamEvent& a = cur.events[cur.cursor];
    const StreamEvent& b = cur.events[next_cur];
    const std::uint64_t dt = b.t_ns > a.t_ns ? b.t_ns - a.t_ns : 0;
    cur.cursor = next_cur;
    (void)do_publish_stream(b);
    const double scale = rate > 0.0 ? rate : 1.0;
    const auto wait_ns = static_cast<std::uint64_t>(static_cast<double>(dt) / scale);
    next_deadline = now + std::chrono::nanoseconds(wait_ns);

    if (at_session_eof()) {
      playing = false;
      emit_eof();
      emit_status(client_fd);
    }
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
          inject_status(kAnsiBye, "DISCONNECTED (replaced by new client)");
          ::close(client_fd);
        }
        client_fd = nfd;
        inbuf.clear();
        char ipbuf[INET_ADDRSTRLEN] = {};
        ::inet_ntop(AF_INET, &peer.sin_addr, ipbuf, sizeof(ipbuf));
        inject_status(kAnsiOk,
                      std::string("CONNECTED from ") + ipbuf + ":"
                          + std::to_string(ntohs(peer.sin_port))
                          + " (listen :" + std::to_string(port) + ")");
        inject_status(kAnsiListen, "waiting GMT session/reset then LOAD A|B");
        emit_hello(client_fd);
        emit_status(client_fd);
      }
    }

    if (client_fd >= 0 && FD_ISSET(client_fd, &rfds)) {
      char buf[4096];
      const ssize_t n = ::recv(client_fd, buf, sizeof(buf), 0);
      if (n <= 0) {
        inject_status(kAnsiBye, "DISCONNECTED (waiting for reconnect)");
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

    try_advance_play();
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

  gf_ara::com::binding::iceoryx::InitRuntime("gf-iox-obs-inject");
  gf_gen::EgoMotionSkeleton ego_pub{};

  if (mode == DriveMode::Playhead) {
    if (!path.empty()) {
      inject_status(kAnsiListen,
                    std::string("session path ignored in playhead stream mode (hint only): ")
                        + path);
    }
    std::cerr << "gf-iox-obs-inject: mode=playhead stream_window"
              << " (do not co-publish with gateway)\n";
    return run_playhead_stream(
        allow, want_ego, ego_pub, parse_control_host(), parse_control_port());
  }

  // continuous: session file required, filtered load + hard max + optional loop
  if (path.empty()) {
    std::cerr << "gf-iox-obs-inject: continuous needs session path argv[1] or GF_INJECT_SESSION\n";
    return EXIT_FAILURE;
  }
  const std::size_t max_events = parse_max_events();
  const bool loop = parse_loop();
  std::string err;
  auto events = load_session_filtered(path, allow, max_events, &err);
  if (!err.empty()) {
    std::cerr << "gf-iox-obs-inject: " << err << "\n";
    return EXIT_FAILURE;
  }
  if (events.empty()) {
    std::cerr << "gf-iox-obs-inject: no allowlisted events in " << path << "\n";
    return EXIT_FAILURE;
  }

  std::cerr << "gf-iox-obs-inject: session=" << path << " events=" << events.size()
            << " max=" << max_events << " mode=continuous"
            << " loop=" << (loop ? "1" : "0")
            << " (do not co-publish with gateway)\n";
  return run_continuous(events, allow, want_ego, ego_pub, loop);
}
