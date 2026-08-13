#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_ara/runtime/process_bringup.hpp"
#include "gf_gen/proxy/ego_motion_proxy.hpp"
#include "gf_gen/proxy/perception_message__out__st_proxy.hpp"
#include "gf_gen/skeleton/trajectory_skeleton.hpp"

#if __has_include("gf_gen/frame_ingest_config.hpp")
#include "gf_gen/frame_ingest_config.hpp"
#define GF_PLAN_HAS_FRAME_INGEST 1
#endif

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
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

constexpr const char* kProcess = "planning.driving";
constexpr int kTrajPoints = 16;
constexpr float kWheelbaseM = 2.8f;
constexpr float kDeg2Rad = 0.017453292519943295f;

struct TruthTip {
  float lead_distance_m{120.0f};
  float lead_rel_speed_mps{0.0f};
  std::string scenario{"none"};
  bool valid{false};
};

struct LongitudinalCtrl {
  float throttle{0.35f};
  float brake{0.0f};
  float steer{0.0f};
  float target_speed_mps{12.0f};
  const char* mode{"cruise"};
};

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

bool JsonStr(const std::string& js, const char* key, std::string* out) {
  const std::string pat = std::string("\"") + key + "\"";
  auto pos = js.find(pat);
  if (pos == std::string::npos) {
    return false;
  }
  pos = js.find(':', pos + pat.size());
  if (pos == std::string::npos) {
    return false;
  }
  pos = js.find('"', pos + 1);
  if (pos == std::string::npos) {
    return false;
  }
  const auto end = js.find('"', pos + 1);
  if (end == std::string::npos) {
    return false;
  }
  *out = js.substr(pos + 1, end - pos - 1);
  return true;
}

TruthTip ReadTruth(const std::string& path) {
  TruthTip t{};
  if (path.empty()) {
    return t;
  }
  std::ifstream in(path);
  if (!in) {
    return t;
  }
  std::ostringstream oss;
  oss << in.rdbuf();
  const std::string js = oss.str();
  float dist = 120.0f;
  float rel = 0.0f;
  std::string sc = "none";
  if (!JsonF32(js, "lead_distance_m", &dist)) {
    return t;
  }
  (void)JsonF32(js, "lead_rel_speed_mps", &rel);
  (void)JsonStr(js, "scenario", &sc);
  t.lead_distance_m = dist;
  t.lead_rel_speed_mps = rel;
  t.scenario = sc;
  t.valid = true;
  return t;
}

void WriteCtrl(const std::string& path, const LongitudinalCtrl& c, std::uint64_t ts) {
  if (path.empty()) {
    return;
  }
  const std::string tmp = path + ".tmp";
  {
    std::ofstream out(tmp, std::ios::trunc);
    if (!out) {
      return;
    }
    out << "{\"throttle\":" << c.throttle << ",\"brake\":" << c.brake
        << ",\"steer\":" << c.steer << ",\"target_speed_mps\":" << c.target_speed_mps
        << ",\"mode\":\"" << c.mode << "\",\"timestamp_ns\":" << ts << "}\n";
  }
  if (std::rename(tmp.c_str(), path.c_str()) != 0) {
    std::remove(tmp.c_str());
  }
}

LongitudinalCtrl ComputeAccAeb(const gf_gen::EgoMotion& ego, const TruthTip& truth) {
  LongitudinalCtrl c{};
  const float v = std::max(0.0f, ego.speed_mps);
  c.steer = std::clamp(ego.steer_angle_deg / 25.0f, -1.0f, 1.0f);

  if (!truth.valid) {
    c.mode = "cruise";
    c.target_speed_mps = 12.0f;
    const float err = c.target_speed_mps - v;
    c.throttle = std::clamp(0.2f + err * 0.08f, 0.0f, 0.7f);
    c.brake = (err < -2.0f) ? std::clamp((-err - 2.0f) * 0.1f, 0.0f, 0.4f) : 0.0f;
    return c;
  }

  const float d = truth.lead_distance_m;
  const float rel = truth.lead_rel_speed_mps;
  // Time-to-collision style AEB.
  const float closing = std::max(0.1f, v - (v + rel));
  const float ttc = d / std::max(0.5f, closing);

  if (truth.scenario == "aeb" || d < 12.0f || ttc < 1.6f) {
    c.mode = "aeb";
    c.target_speed_mps = 0.0f;
    c.throttle = 0.0f;
    c.brake = (d < 6.0f || ttc < 1.0f) ? 1.0f : std::clamp(0.55f + (12.0f - d) * 0.05f, 0.55f, 1.0f);
    return c;
  }

  // ACC: hold ~gap_time * speed, clamp gap 18–40 m.
  c.mode = "acc";
  const float desired_gap = std::clamp(v * 1.6f, 18.0f, 40.0f);
  const float gap_err = d - desired_gap;
  c.target_speed_mps = std::clamp(v + gap_err * 0.15f + rel * 0.4f, 0.0f, 16.0f);
  const float speed_err = c.target_speed_mps - v;
  if (speed_err >= 0.0f) {
    c.throttle = std::clamp(0.15f + speed_err * 0.1f, 0.0f, 0.65f);
    c.brake = 0.0f;
  } else {
    c.throttle = 0.0f;
    c.brake = std::clamp((-speed_err) * 0.12f, 0.0f, 0.7f);
  }
  return c;
}

void FillCurvedTrajectory(const gf_gen::EgoMotion& ego,
                          float speed_scale,
                          gf_gen::Trajectory& traj) {
  const float speed = std::max(ego.speed_mps * speed_scale, 0.2f);
  const float yaw_rate_rad = ego.yaw_rate_degps * kDeg2Rad;
  const float steer_rad = ego.steer_angle_deg * kDeg2Rad;

  float kappa = 0.0f;
  if (std::fabs(yaw_rate_rad) > 1e-4f) {
    kappa = yaw_rate_rad / std::max(speed, 0.5f);
  } else {
    kappa = steer_rad / kWheelbaseM;
  }
  kappa *= 2.5f;
  constexpr float kMaxKappa = 0.15f;
  kappa = std::clamp(kappa, -kMaxKappa, kMaxKappa);

  const float horizon_m = std::clamp(speed * 3.0f, 20.0f, 55.0f);
  const float ds = horizon_m / static_cast<float>(kTrajPoints - 1);
  float x = 0.0f;
  float y = 0.0f;
  float psi = 0.0f;

  traj.timestamp_ns = ego.timestamp_ns;
  traj.point_count = static_cast<std::uint8_t>(kTrajPoints);
  traj.gear_shift_first = ego.gear;
  traj.gear_shift_second = 0;

  for (int i = 0; i < kTrajPoints; ++i) {
    traj.points_x_m[i] = x;
    traj.points_y_m[i] = y;
    psi += kappa * ds;
    x += ds * std::cos(psi);
    y += ds * std::sin(psi);
  }
}

std::string TruthPath() {
  const char* v = std::getenv("GF_CARLA_TRUTH_PATH");
#if defined(GF_PLAN_HAS_FRAME_INGEST)
  if (!v || !v[0]) {
    v = gf_gen::frame_ingest::kTruthPath;
  }
#endif
  return (v && v[0]) ? std::string(v) : std::string("/tmp/gf_carla_truth.json");
}

std::string CtrlPath() {
  const char* v = std::getenv("GF_PLANNING_CTRL_PATH");
#if defined(GF_PLAN_HAS_FRAME_INGEST)
  if (!v || !v[0]) {
    v = gf_gen::frame_ingest::kCtrlPath;
  }
#endif
  return (v && v[0]) ? std::string(v) : std::string("/tmp/gf_planning_ctrl.json");
}

}  // namespace

int main() {
  gf_ara::com::binding::iceoryx::InitRuntime("gf-planning-driving");

  gf_ara::runtime::ProcessSupervisor supervisor;
  if (!supervisor.Start(kProcess)) {
    return EXIT_FAILURE;
  }

  gf_gen::Perception_MESSAGE_Out_StProxy perc_sub{};
  gf_gen::EgoMotionProxy ego_sub{};
  gf_gen::TrajectorySkeleton traj_pub{};

  std::optional<gf_gen::Perception_MESSAGE_Out_St> last_perc;
  std::optional<gf_gen::EgoMotion> last_ego;
  std::uint64_t seq = 0;
  const std::string truth_path = TruthPath();
  const std::string ctrl_path = CtrlPath();

  std::cout << "gf-planning-driving: start (ACC/AEB truth=" << truth_path
            << " ctrl=" << ctrl_path << ")\n";

  while (!iox::posix::hasTerminationRequested()) {
    supervisor.Tick();
    if (supervisor.ExitForEmRestart()) {
      return gf_ara::exec::kEmRestartExitCode;
    }

    if (auto t = perc_sub.Take(); t && t.Value().has_value()) {
      last_perc = *t.Value();
    }
    if (auto t = ego_sub.Take(); t && t.Value().has_value()) {
      last_ego = *t.Value();
    }

    if (last_ego) {
      const auto& ego = *last_ego;
      const int dyn =
          last_perc ? static_cast<int>(last_perc->dyn_obj_count) : 0;
      const TruthTip truth = ReadTruth(truth_path);
      const LongitudinalCtrl ctrl = ComputeAccAeb(ego, truth);
      WriteCtrl(ctrl_path, ctrl, ego.timestamp_ns);

      float speed_scale = 1.0f;
      if (std::strcmp(ctrl.mode, "aeb") == 0) {
        speed_scale = 0.15f;
      } else if (std::strcmp(ctrl.mode, "acc") == 0) {
        speed_scale = std::clamp(ctrl.target_speed_mps / std::max(ego.speed_mps, 1.0f),
                                 0.3f, 1.2f);
      }

      gf_gen::Trajectory traj{};
      FillCurvedTrajectory(ego, speed_scale, traj);
      if (static_cast<bool>(traj_pub.Send(traj))) {
        std::cout << "gf-planning-driving: Trajectory#" << seq
                  << " pts=" << static_cast<int>(traj.point_count)
                  << " y_end=" << traj.points_y_m[traj.point_count - 1]
                  << " dyn=" << dyn << " mode=" << ctrl.mode
                  << " lead=" << (truth.valid ? truth.lead_distance_m : -1.0f)
                  << " thr=" << ctrl.throttle << " brk=" << ctrl.brake
                  << std::endl;
        ++seq;
      }
      last_ego.reset();
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
  }
  return EXIT_SUCCESS;
}
