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
#include <string>
#include <thread>

namespace {

constexpr const char* kProcess = "planning.driving";
constexpr int kTrajPoints = 16;
// First-cut lane-keep gains (tune later).
constexpr float kBlendLenM = 18.0f;     // approach lane center over ~this length
constexpr float kSteerKy = 0.35f;       // 1/m → steer from lateral error
constexpr float kSteerKpsi = 0.80f;     // steer from heading (C1)
constexpr float kMaxSteer = 0.55f;

struct LeadSnapshot {
  float lead_distance_m{130.0f};
  float lead_rel_speed_mps{0.0f};
  bool valid{false};
};

struct LongitudinalCtrl {
  float throttle{0.35f};
  float brake{0.0f};
  float steer{0.0f};
  float target_speed_mps{12.0f};
  const char* mode{"cruise"};
};

struct HostLaneGeom {
  bool valid{false};
  float c0{0.0f};  // lane-center poly (ego-frame y left)
  float c1{0.0f};
  float c2{0.0f};
  float c3{0.0f};
  float x_end{60.0f};
  float width_m{3.5f};
  float e_y{0.0f};  // y_center(0): >0 → center is left of ego

  float y_at(float x) const {
    return c0 + c1 * x + c2 * x * x + c3 * x * x * x;
  }
};

LeadSnapshot LeadFromPerc(const gf_gen::Perception_MESSAGE_Out_St& perc) {
  LeadSnapshot t{};
  const auto& dyn = perc.Perception_DYN_OBJ_Out;
  if (dyn.m_OBJ_VD_Count == 0) {
    return t;
  }
  std::uint8_t idx = 0;
  if (dyn.m_OBJ_VD_CIPV_ID != 0) {
    for (std::uint8_t i = 0; i < dyn.m_OBJ_VD_Count && i < 13; ++i) {
      if (dyn.m_Obj_item[i].m_OBJ_ID == dyn.m_OBJ_VD_CIPV_ID) {
        idx = i;
        break;
      }
    }
  }
  const auto& obj = dyn.m_Obj_item[idx];
  if (obj.m_OBJ_ID == 0 || obj.m_OBJ_Long_Distance <= 0.5f ||
      obj.m_OBJ_Long_Distance > 130.0f) {
    return t;
  }
  t.lead_distance_m = obj.m_OBJ_Long_Distance;
  t.lead_rel_speed_mps = obj.m_OBJ_Relative_Long_Velocity;
  t.valid = true;
  return t;
}

HostLaneGeom HostLaneFromPerc(const gf_gen::Perception_MESSAGE_Out_St& perc) {
  HostLaneGeom g{};
  const auto& lh = perc.Perception_LH_Out;
  if (lh.m_hostline_num < 1) {
    return g;
  }
  bool have_l = false;
  bool have_r = false;
  float lc0 = 0.0f, lc1 = 0.0f, lc2 = 0.0f, lc3 = 0.0f, lx1 = 60.0f;
  float rc0 = 0.0f, rc1 = 0.0f, rc2 = 0.0f, rc3 = 0.0f, rx1 = 60.0f;
  const std::uint8_t n = std::min<std::uint8_t>(lh.m_hostline_num, 4);
  for (std::uint8_t i = 0; i < n; ++i) {
    const auto& line = lh.m_hostline[i];
    if (line.m_LH_Confidence < 0.1f && line.m_LH_Availability_State == 0) {
      continue;
    }
    const float x1 = std::max(line.m_LH_First_VR_End, 20.0f);
    // side: 1=left, 2=right (FCM convention)
    if (line.m_LH_Side == 1) {
      have_l = true;
      lc0 = line.m_LH_Line_First_C0;
      lc1 = line.m_LH_Line_First_C1;
      lc2 = line.m_LH_Line_First_C2;
      lc3 = line.m_LH_Line_First_C3;
      lx1 = x1;
    } else if (line.m_LH_Side == 2) {
      have_r = true;
      rc0 = line.m_LH_Line_First_C0;
      rc1 = line.m_LH_Line_First_C1;
      rc2 = line.m_LH_Line_First_C2;
      rc3 = line.m_LH_Line_First_C3;
      rx1 = x1;
    }
  }
  if (have_l && have_r) {
    g.valid = true;
    g.c0 = 0.5f * (lc0 + rc0);
    g.c1 = 0.5f * (lc1 + rc1);
    g.c2 = 0.5f * (lc2 + rc2);
    g.c3 = 0.5f * (lc3 + rc3);
    g.x_end = std::min(lx1, rx1);
    g.width_m = std::max(2.5f, std::fabs(lc0 - rc0));
  } else if (have_l || have_r) {
    // One edge only: assume ~3.5 m lane, ego near center of half-width.
    g.valid = true;
    const float half = 1.75f;
    if (have_l) {
      g.c0 = lc0 - half;
      g.c1 = lc1;
      g.c2 = lc2;
      g.c3 = lc3;
      g.x_end = lx1;
    } else {
      g.c0 = rc0 + half;
      g.c1 = rc1;
      g.c2 = rc2;
      g.c3 = rc3;
      g.x_end = rx1;
    }
    g.width_m = 3.5f;
  }
  if (lh.m_LH_Estimated_Width > 0.5f) {
    g.width_m = lh.m_LH_Estimated_Width;
  }
  g.e_y = g.y_at(0.0f);
  return g;
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

float SteerFromLane(const HostLaneGeom& lane) {
  if (!lane.valid) {
    return 0.0f;
  }
  // Ego-frame y>0 is left. CARLA steer>0 is right → negate lateral/heading terms.
  const float cmd = -kSteerKy * lane.e_y - kSteerKpsi * lane.c1;
  return std::clamp(cmd, -kMaxSteer, kMaxSteer);
}

LongitudinalCtrl ComputeAccAeb(const gf_gen::EgoMotion& ego,
                               const LeadSnapshot& lead,
                               const HostLaneGeom& lane) {
  LongitudinalCtrl c{};
  const float v = std::max(0.0f, ego.speed_mps);
  c.steer = lane.valid ? SteerFromLane(lane)
                       : std::clamp(ego.steer_angle_deg / 25.0f, -1.0f, 1.0f);

  if (!lead.valid) {
    c.mode = "cruise";
    c.target_speed_mps = 12.0f;
    const float err = c.target_speed_mps - v;
    // Standstill pull-away: need a real throttle floor or CARLA never starts.
    if (v < 0.8f) {
      c.throttle = std::clamp(0.45f + err * 0.05f, 0.40f, 0.75f);
      c.brake = 0.0f;
    } else {
      c.throttle = std::clamp(0.2f + err * 0.08f, 0.0f, 0.7f);
      c.brake = (err < -2.0f) ? std::clamp((-err - 2.0f) * 0.1f, 0.0f, 0.4f) : 0.0f;
    }
    return c;
  }

  const float d = lead.lead_distance_m;
  const float rel = lead.lead_rel_speed_mps;
  // Closing rate: ego closing on lead (positive when approaching).
  const float closing = std::max(0.0f, -rel);
  const float ttc = (closing > 0.5f) ? (d / closing) : 1.0e6f;

  // Hard AEB only when actually moving into a near threat (not parked at gap).
  if (d < 5.0f || (v > 1.2f && (d < 10.0f || ttc < 1.4f))) {
    c.mode = "aeb";
    c.target_speed_mps = 0.0f;
    c.throttle = 0.0f;
    c.brake = (d < 5.0f || ttc < 1.0f) ? 1.0f
                                        : std::clamp(0.55f + (10.0f - d) * 0.05f, 0.55f, 1.0f);
    return c;
  }

  c.mode = "acc";
  // Gap scales with speed; floor is creep-friendly (old 18 m floor pinned v=0).
  const float desired_gap = std::clamp(std::max(8.0f, v * 1.6f), 8.0f, 40.0f);
  const float gap_err = d - desired_gap;

  // Pull-away: stopped with a safe gap ahead → accelerate toward cruise/follow.
  if (v < 1.0f && d > 10.0f) {
    const float pull = std::clamp(8.0f + gap_err * 0.2f + rel * 0.3f, 6.0f, 12.0f);
    c.target_speed_mps = pull;
    c.throttle = std::clamp(0.42f + (pull - v) * 0.06f, 0.35f, 0.75f);
    c.brake = 0.0f;
    c.mode = "pullaway";
    return c;
  }

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

void FillLaneKeepTrajectory(const gf_gen::EgoMotion& ego,
                            float speed_scale,
                            const HostLaneGeom& lane,
                            gf_gen::Trajectory& traj) {
  const float speed = std::max(ego.speed_mps * speed_scale, 0.2f);
  const float horizon_m =
      std::clamp(speed * 4.0f, 25.0f, std::min(100.0f, lane.valid ? lane.x_end : 100.0f));
  const float ds = horizon_m / static_cast<float>(kTrajPoints - 1);

  traj.timestamp_ns = ego.timestamp_ns;
  traj.point_count = static_cast<std::uint8_t>(kTrajPoints);
  traj.gear_shift_first = ego.gear;
  traj.gear_shift_second = 0;

  for (int i = 0; i < kTrajPoints; ++i) {
    const float x = ds * static_cast<float>(i);
    float y = 0.0f;
    if (lane.valid) {
      // Ego at (0,0); blend onto lane-center poly so path stays in-lane.
      const float alpha = 1.0f - std::exp(-x / kBlendLenM);
      y = alpha * lane.y_at(x);
    }
    traj.points_x_m[i] = x;
    traj.points_y_m[i] = y;
  }
}

std::string CtrlPath() {
  const char* v = std::getenv("GF_PLANNING_CTRL_PATH");
#if defined(GF_PLAN_HAS_FRAME_INGEST)
  if (!v || !v[0]) {
    v = gf_gen::frame_ingest::kCtrlPath;
  }
#endif
  return (v && v[0]) ? std::string(v) : std::string("runtime_ipc/planning_ctrl.json");
}

}  // namespace

int main() {
  gf_ara::com::binding::iceoryx::InitRuntime("gf-planning-driving");

  gf_ara::runtime::ProcessSupervisor supervisor;
  if (!supervisor.Start(kProcess)) {
    std::cerr << "[ERROR] planning.driving: ProcessSupervisor.Start failed\n";
    return EXIT_FAILURE;
  }

  gf_gen::Perception_MESSAGE_Out_StProxy perc_sub{};
  gf_gen::EgoMotionProxy ego_sub{};
  gf_gen::TrajectorySkeleton traj_pub{};

  std::optional<gf_gen::Perception_MESSAGE_Out_St> last_perc;
  std::optional<gf_gen::EgoMotion> last_ego;
  std::uint64_t seq = 0;
  const std::string ctrl_path = CtrlPath();

  std::cout << "gf-planning-driving: start (ACC/AEB + LH lane-keep; ctrl=" << ctrl_path
            << ")\n";

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
      LeadSnapshot lead{};
      HostLaneGeom lane{};
      int dyn = 0;
      int lh_n = 0;
      if (last_perc) {
        lead = LeadFromPerc(*last_perc);
        lane = HostLaneFromPerc(*last_perc);
        dyn = static_cast<int>(last_perc->Perception_DYN_OBJ_Out.m_OBJ_VD_Count);
        lh_n = static_cast<int>(last_perc->Perception_LH_Out.m_hostline_num);
      }
      const LongitudinalCtrl ctrl = ComputeAccAeb(ego, lead, lane);
      WriteCtrl(ctrl_path, ctrl, ego.timestamp_ns);

      float speed_scale = 1.0f;
      if (std::strcmp(ctrl.mode, "aeb") == 0) {
        speed_scale = 0.15f;
      } else if (std::strcmp(ctrl.mode, "acc") == 0 ||
                 std::strcmp(ctrl.mode, "pullaway") == 0) {
        speed_scale = std::clamp(ctrl.target_speed_mps / std::max(ego.speed_mps, 1.0f),
                                 0.3f, 1.2f);
      }

      // When parked, shape traj from commanded speed so BEV path isn't a stub.
      gf_gen::EgoMotion ego_for_traj = ego;
      if (ego.speed_mps < 1.0f && ctrl.target_speed_mps > 1.0f &&
          std::strcmp(ctrl.mode, "aeb") != 0) {
        ego_for_traj.speed_mps = ctrl.target_speed_mps;
      }
      gf_gen::Trajectory traj{};
      FillLaneKeepTrajectory(ego_for_traj, speed_scale, lane, traj);
      if (static_cast<bool>(traj_pub.Send(traj))) {
        std::cout << "gf-planning-driving: Trajectory#" << seq
                  << " pts=" << static_cast<int>(traj.point_count)
                  << " y_end=" << traj.points_y_m[traj.point_count - 1]
                  << " e_y=" << lane.e_y << " lh=" << lh_n
                  << " lane=" << (lane.valid ? 1 : 0)
                  << " dyn=" << dyn << " mode=" << ctrl.mode
                  << " lead=" << (lead.valid ? lead.lead_distance_m : -1.0f)
                  << " thr=" << ctrl.throttle << " brk=" << ctrl.brake
                  << " st=" << ctrl.steer
                  << std::endl;
        ++seq;
      }
      last_ego.reset();
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
  }
  return EXIT_SUCCESS;
}
