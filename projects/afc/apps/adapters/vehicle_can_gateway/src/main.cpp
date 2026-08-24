#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_ara/runtime/process_bringup.hpp"
#include "gf_gen/proxy/trajectory_proxy.hpp"
#include "gf_gen/skeleton/ego_motion_skeleton.hpp"
#include "gf_gen/skeleton/perception__in__st_skeleton.hpp"

#if __has_include("gf_gen/frame_ingest_config.hpp")
#include "gf_gen/frame_ingest_config.hpp"
#define GF_GW_HAS_FRAME_INGEST 1
#endif

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <optional>
#include <sstream>
#include <string>
#include <thread>

namespace {

constexpr const char* kProcess = "adapter.vehicle_can_gateway";

std::uint64_t now_ns() {
  return static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(
          std::chrono::steady_clock::now().time_since_epoch())
          .count());
}

const char* LaneFromYEnd(float y_end) {
  if (y_end > 0.4f) {
    return "left";
  }
  if (y_end < -0.4f) {
    return "right";
  }
  return "none";
}

bool JsonF32(const std::string& js, const char* key, float* out) {
  const std::string pat = std::string("\"") + key + "\"";
  auto pos = js.find(pat);
  if (pos == std::string::npos) {
    return false;
  }
  pos = js.find(':', pos + pat.size());
  if (pos == std::string::npos) {
    return false;
  }
  ++pos;
  while (pos < js.size() && (js[pos] == ' ' || js[pos] == '\t')) {
    ++pos;
  }
  char* end = nullptr;
  const float v = std::strtof(js.c_str() + pos, &end);
  if (end == js.c_str() + pos) {
    return false;
  }
  *out = v;
  return true;
}

bool JsonU64(const std::string& js, const char* key, std::uint64_t* out) {
  const std::string pat = std::string("\"") + key + "\"";
  auto pos = js.find(pat);
  if (pos == std::string::npos) {
    return false;
  }
  pos = js.find(':', pos + pat.size());
  if (pos == std::string::npos) {
    return false;
  }
  ++pos;
  while (pos < js.size() && (js[pos] == ' ' || js[pos] == '\t')) {
    ++pos;
  }
  char* end = nullptr;
  const unsigned long long v = std::strtoull(js.c_str() + pos, &end, 10);
  if (end == js.c_str() + pos) {
    return false;
  }
  *out = static_cast<std::uint64_t>(v);
  return true;
}

bool JsonU8(const std::string& js, const char* key, std::uint8_t* out) {
  std::uint64_t v = 0;
  if (!JsonU64(js, key, &v)) {
    return false;
  }
  *out = static_cast<std::uint8_t>(v);
  return true;
}

std::optional<std::string> ReadText(const std::string& path) {
  std::ifstream in(path);
  if (!in) {
    return std::nullopt;
  }
  std::ostringstream oss;
  oss << in.rdbuf();
  return oss.str();
}

struct CtrlSnapshot {
  float throttle{0.0f};
  float brake{0.0f};
  float steer{0.0f};
  bool has_longitudinal{false};
};

CtrlSnapshot ReadCtrl(const std::string& path) {
  CtrlSnapshot c{};
  if (path.empty()) {
    return c;
  }
  auto js = ReadText(path);
  if (!js) {
    return c;
  }
  float thr = 0.0f;
  float brk = 0.0f;
  float st = 0.0f;
  const bool ht = JsonF32(*js, "throttle", &thr);
  const bool hb = JsonF32(*js, "brake", &brk);
  const bool hs = JsonF32(*js, "steer", &st);
  if (ht || hb || hs) {
    c.has_longitudinal = true;
    c.throttle = thr;
    c.brake = brk;
    c.steer = st;
  }
  return c;
}

bool FillEgoFromCarlaTip(const std::string& path, gf_gen::EgoMotion* ego) {
  auto js = ReadText(path);
  if (!js) {
    return false;
  }
  float speed = 0.0f;
  float yaw = 0.0f;
  float steer = 0.0f;
  std::uint8_t gear = 4;
  std::uint64_t ts = 0;
  if (!JsonF32(*js, "speed_mps", &speed)) {
    return false;
  }
  (void)JsonF32(*js, "yaw_rate_degps", &yaw);
  (void)JsonF32(*js, "steer_angle_deg", &steer);
  (void)JsonU8(*js, "gear", &gear);
  if (!JsonU64(*js, "timestamp_ns", &ts)) {
    ts = now_ns();
  }
  ego->timestamp_ns = ts;
  ego->speed_mps = speed;
  ego->yaw_rate_degps = yaw;
  ego->steer_angle_deg = steer;
  ego->gear = gear;
  return true;
}

void WriteCarlaCmd(const std::string& path,
                   const char* lane,
                   float speed_mps,
                   float throttle,
                   float brake,
                   float steer,
                   std::uint64_t seq) {
  if (path.empty()) {
    return;
  }
  const std::string tmp = path + ".tmp";
  {
    std::ofstream out(tmp, std::ios::trunc);
    if (!out) {
      return;
    }
    out << "{\"lane_change\":\"" << lane << "\",\"speed_mps\":" << speed_mps
        << ",\"throttle\":" << throttle << ",\"brake\":" << brake
        << ",\"steer\":" << steer << ",\"seq\":" << seq
        << ",\"timestamp_ns\":" << now_ns() << "}\n";
  }
  if (std::rename(tmp.c_str(), path.c_str()) != 0) {
    std::remove(tmp.c_str());
  }
}

const char* EgoSource() {
  const char* v = std::getenv("GF_EGO_SOURCE");
#if defined(GF_GW_HAS_FRAME_INGEST)
  if (!v || !v[0]) {
    v = gf_gen::frame_ingest::kEgoSource;
  }
#endif
  return (v && v[0]) ? v : "gateway";
}

}  // namespace

int main(int argc, char** argv) {
  int max_traj = 0;
  if (argc > 1) {
    max_traj = std::atoi(argv[1]);
  }

  gf_ara::com::binding::iceoryx::InitRuntime("gf-vehicle-can-gateway");

  gf_ara::runtime::ProcessSupervisor supervisor;
  if (!supervisor.Start(kProcess)) {
    std::cerr << "[ERROR] vehicle_can_gateway: ProcessSupervisor.Start failed\n";
    return EXIT_FAILURE;
  }

  const char* cmd_env = std::getenv("GF_CARLA_CMD_PATH");
  std::string cmd_path = (cmd_env && cmd_env[0]) ? cmd_env : "";
  const char* ego_env = std::getenv("GF_CARLA_EGO_PATH");
  std::string ego_path = (ego_env && ego_env[0]) ? ego_env : "";
  const char* ctrl_env = std::getenv("GF_PLANNING_CTRL_PATH");
  std::string ctrl_path = (ctrl_env && ctrl_env[0]) ? ctrl_env : "";

#if defined(GF_GW_HAS_FRAME_INGEST)
  if (cmd_path.empty() && gf_gen::frame_ingest::kBridgeEnabled) {
    cmd_path = gf_gen::frame_ingest::kCmdPath;
  }
  if (ego_path.empty()) {
    ego_path = gf_gen::frame_ingest::kEgoPath;
  }
  if (ctrl_path.empty()) {
    ctrl_path = gf_gen::frame_ingest::kCtrlPath;
  }
#else
  if (ego_path.empty()) {
    ego_path = "runtime_ipc/carla_ego.json";
  }
  if (ctrl_path.empty()) {
    ctrl_path = "runtime_ipc/planning_ctrl.json";
  }
#endif

  const std::string ego_src = EgoSource();
  const bool ego_from_carla = (ego_src == "carla");

  // Mutual exclusion: inject owns EgoMotion — gateway must not double-publish.
  if (ego_src == "inject") {
    std::cerr << "gf-vehicle-can-gateway: ego_source=inject — exit "
                 "(inject owns EgoMotion; do not dual-publish)\n";
    return EXIT_SUCCESS;
  }

  gf_gen::EgoMotionSkeleton ego_pub{};
  gf_gen::Perception_In_StSkeleton perc_in_pub{};
  gf_gen::TrajectoryProxy traj_sub{};

  std::uint64_t frame = 0;
  int got_traj = 0;
  std::uint64_t cmd_seq = 0;
  std::string last_lane = "none";
  gf_gen::EgoMotion last_ego{};
  bool have_ego = false;

  std::cout << "gf-vehicle-can-gateway: start ego_source=" << ego_src;
  if (max_traj > 0) {
    std::cout << " (exit after " << max_traj << " Trajectory)";
  }
  if (!cmd_path.empty()) {
    std::cout << " carla_cmd=" << cmd_path;
  }
  std::cout << std::endl;

  while (!iox::posix::hasTerminationRequested()) {
    supervisor.Tick();
    if (supervisor.ExitForEmRestart()) {
      return gf_ara::exec::kEmRestartExitCode;
    }

    gf_gen::EgoMotion ego{};
    if (ego_from_carla) {
      if (!FillEgoFromCarlaTip(ego_path, &ego)) {
        if (have_ego) {
          ego = last_ego;
          ego.timestamp_ns = now_ns();
        } else {
          // Wait for first camera frame from carla_bridge.
          std::this_thread::sleep_for(std::chrono::milliseconds(20));
          ++frame;
          continue;
        }
      } else {
        have_ego = true;
        last_ego = ego;
      }
    } else {
      ego.timestamp_ns = now_ns();
      ego.speed_mps = 5.0f + static_cast<float>(frame % 10) * 0.1f;
      ego.yaw_rate_degps = 0.1f;
      ego.steer_angle_deg = 2.0f;
      ego.gear = 4;
    }
    (void)ego_pub.Send(ego);

    gf_gen::Perception_In_St pin{};
    pin.timestamp_ns = ego.timestamp_ns;
    pin.ipc_frame_counter = static_cast<std::uint32_t>(frame);
    pin.gear = ego.gear;
    pin.vehicle_speed = ego.speed_mps;
    pin.yaw_rate = ego.yaw_rate_degps;
    pin._vendor_payload_opaque[0] = 0;
    (void)perc_in_pub.Send(pin);

    const char* lane = "none";
    float y_end = 0.0f;
    auto taken = traj_sub.Take();
    if (taken && taken.Value().has_value()) {
      const auto& t = *taken.Value();
      ++got_traj;
      if (t.point_count > 0) {
        y_end = t.points_y_m[t.point_count - 1];
        lane = LaneFromYEnd(y_end);
      }
      std::cout << "gf-vehicle-can-gateway: Trajectory#" << got_traj
                << " points=" << static_cast<int>(t.point_count)
                << " y_end=" << y_end << " lane=" << lane
                << " ts_ns=" << t.timestamp_ns << std::endl;
      if (max_traj > 0 && got_traj >= max_traj) {
        std::cout << "gf-vehicle-can-gateway: received " << got_traj
                  << " Trajectory sample(s), exiting OK\n";
        return EXIT_SUCCESS;
      }
    }

    if (!cmd_path.empty()) {
      // Lane / longitudinal intent from planning (+ optional ctrl snapshot).
      // World scripted maneuvers belong in carla_scenarios/*.py — not gateway demos.
      const CtrlSnapshot ctrl = ReadCtrl(ctrl_path);
      float thr = ctrl.has_longitudinal ? ctrl.throttle : 0.35f;
      float brk = ctrl.has_longitudinal ? ctrl.brake : 0.0f;
      float st = ctrl.has_longitudinal ? ctrl.steer : 0.0f;
      if (!ctrl.has_longitudinal) {
        if (std::strcmp(lane, "left") == 0) {
          st = 0.25f;
        } else if (std::strcmp(lane, "right") == 0) {
          st = -0.25f;
        }
      }

      if (lane != last_lane || (got_traj > 0 && (got_traj % 5) == 0) ||
          ctrl.has_longitudinal) {
        ++cmd_seq;
        WriteCarlaCmd(cmd_path, lane, ego.speed_mps, thr, brk, st, cmd_seq);
        if (lane != last_lane) {
          std::cout << "gf-vehicle-can-gateway: wrote carla_cmd seq=" << cmd_seq
                    << " lane_change=" << lane << " thr=" << thr
                    << " brk=" << brk << " steer=" << st << std::endl;
          last_lane = lane;
        }
      }
    }

    ++frame;
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
  }
  return EXIT_SUCCESS;
}
