#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_ara/runtime/process_bringup.hpp"
#include "gf_gen/proxy/ego_motion_proxy.hpp"
#include "gf_gen/proxy/perception_message__out__st_proxy.hpp"
#include "gf_gen/skeleton/trajectory_skeleton.hpp"

#include "m_lon_acc_aeb.hpp"
#include "m_lat_lka.hpp"
#include "m_lat_traj.hpp"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <optional>
#include <thread>

namespace {

constexpr const char* kProcess = "planning.driving";

struct LeadSnapshot {
  float lead_distance_m{130.0f};
  float lead_rel_speed_mps{0.0f};
  bool valid{false};
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

std::uint8_t CtrlModeId(const char* mode) {
  if (!mode) {
    return 0;
  }
  if (std::strcmp(mode, "acc") == 0) {
    return 1;
  }
  if (std::strcmp(mode, "aeb") == 0) {
    return 2;
  }
  if (std::strcmp(mode, "pullaway") == 0) {
    return 3;
  }
  return 0;  // cruise
}

void ApplyLatTraj(const oct_gen::LatTraj& path, const gf_gen::EgoMotion& ego,
                  const oct_gen::LonCtrl& lon, float steer, gf_gen::Trajectory& traj) {
  traj.timestamp_ns = ego.timestamp_ns;
  traj.point_count = static_cast<std::uint8_t>(oct_gen::kLatTrajPoints);
  traj.gear_shift_first = ego.gear;
  traj.gear_shift_second = 0;
  for (int i = 0; i < oct_gen::kLatTrajPoints; ++i) {
    traj.points_x_m[i] = path.x_m[i];
    traj.points_y_m[i] = path.y_m[i];
  }
  traj.throttle = lon.throttle;
  traj.brake = lon.brake;
  traj.steer = steer;
  traj.target_speed_mps = lon.target_speed_mps;
  traj.ctrl_mode = CtrlModeId(lon.mode);
}

/** Soft brake + steer slew when off-center / no LH; AEB freezes steer (lite shell). */
void ApplyLatLonGuard(oct_gen::LonCtrl* lon, float* steer, bool lane_valid, float e_y,
                      float lane_width_m, float speed_mps, float* last_steer) {
  constexpr float kSteerRate = 0.08f;
  const float width = std::max(2.5f, lane_width_m > 0.5f ? lane_width_m : 3.5f);
  const float off = std::fabs(e_y);
  if (!lane_valid) {
    lon->throttle = 0.0f;
    lon->brake = std::max(lon->brake, 0.35f);
    lon->target_speed_mps = std::min(lon->target_speed_mps, 2.0f);
  } else if (off > 0.6f * width) {
    lon->throttle = std::min(lon->throttle, 0.08f);
    lon->brake = std::max(lon->brake, 0.22f);
    lon->target_speed_mps =
        std::min(lon->target_speed_mps, std::max(3.0f, speed_mps * 0.55f));
  }
  // AEB: do not center-yank while hard-braking; cruise/ACC keep LKA.
  if (lon->mode && std::strcmp(lon->mode, "aeb") == 0) {
    *steer = 0.0f;
  }
  const float ds = std::clamp(*steer - *last_steer, -kSteerRate, kSteerRate);
  *steer = *last_steer + ds;
  *last_steer = *steer;
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
  float last_steer = 0.0f;

  std::cout << "gf-planning-driving: start (ACC/AEB + LH lane-keep; ctrl via Trajectory)\n";

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
      auto lon = oct_gen::m_lon_acc_aeb(
          ego.speed_mps, lead.valid, lead.lead_distance_m, lead.lead_rel_speed_mps);
      float steer = oct_gen::m_lat_lka(lane.valid, lane.e_y, lane.c1,
                                       ego.steer_angle_deg);
      ApplyLatLonGuard(&lon, &steer, lane.valid, lane.e_y, lane.width_m, ego.speed_mps,
                       &last_steer);

      float speed_scale = 1.0f;
      if (std::strcmp(lon.mode, "aeb") == 0) {
        speed_scale = 0.15f;
      } else if (std::strcmp(lon.mode, "acc") == 0 ||
                 std::strcmp(lon.mode, "pullaway") == 0) {
        speed_scale = std::clamp(lon.target_speed_mps / std::max(ego.speed_mps, 1.0f),
                                 0.3f, 1.2f);
      }
      if (!lane.valid || std::fabs(lane.e_y) > 0.6f * std::max(2.5f, lane.width_m)) {
        speed_scale = std::min(speed_scale, 0.4f);
      }

      // When parked, shape traj from commanded speed so BEV path isn't a stub.
      float speed_for_path = ego.speed_mps;
      if (ego.speed_mps < 1.0f && lon.target_speed_mps > 1.0f &&
          std::strcmp(lon.mode, "aeb") != 0) {
        speed_for_path = lon.target_speed_mps;
      }
      const auto path = oct_gen::m_lat_traj(speed_for_path, speed_scale, lane.valid, lane.c0,
                                            lane.c1, lane.c2, lane.c3, lane.x_end);
      gf_gen::Trajectory traj{};
      ApplyLatTraj(path, ego, lon, steer, traj);
      if (static_cast<bool>(traj_pub.Send(traj))) {
        std::cout << "gf-planning-driving: Trajectory#" << seq
                  << " pts=" << static_cast<int>(traj.point_count)
                  << " y_end=" << traj.points_y_m[traj.point_count - 1]
                  << " e_y=" << lane.e_y << " lh=" << lh_n
                  << " lane=" << (lane.valid ? 1 : 0)
                  << " dyn=" << dyn << " mode=" << lon.mode
                  << " lead=" << (lead.valid ? lead.lead_distance_m : -1.0f)
                  << " thr=" << traj.throttle << " brk=" << traj.brake
                  << " st=" << traj.steer
                  << std::endl;
        ++seq;
      }
      last_ego.reset();
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
  }
  return EXIT_SUCCESS;
}
