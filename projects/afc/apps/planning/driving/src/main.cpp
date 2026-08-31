#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_ara/runtime/process_bringup.hpp"
#include "gf_gen/proxy/ego_motion_proxy.hpp"
#include "gf_gen/proxy/perception_message__out__st_proxy.hpp"
#include "gf_gen/skeleton/trajectory_skeleton.hpp"

#include "gf_app/frame_watch.hpp"

#include "m_plan_tick.hpp"

#include "gf_octave_planning/plan_cal.hpp"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <optional>
#include <string>
#include <thread>

namespace {

constexpr const char* kProcess = "planning.driving";
constexpr int kDynCap = 13;
constexpr float kObjDMaxM = 130.0f;

int LogEvery() {
  const char* v = std::getenv("GF_APP_LOG_EVERY");
  if (!v || !v[0]) {
    return 40;
  }
  const int n = std::atoi(v);
  return n < 1 ? 1 : n;
}

bool FMoved(float a, float b, float eps) { return std::fabs(a - b) > eps; }

struct HostLaneGeom {
  bool valid{false};
  float c0{0.0f};
  float c1{0.0f};
  float c2{0.0f};
  float c3{0.0f};
  float x_end{60.0f};
  float width_m{3.5f};
  float e_y{0.0f};
  float conf{1.0f};
  float lane_count{1.0f};

  float y_at(float x) const {
    return c0 + c1 * x + c2 * x * x + c3 * x * x * x;
  }
};

struct PercView {
  HostLaneGeom lane{};
  oct_gen::PlanObj obj[oct_gen::kObjNMax]{};
  int nobj{0};
  int dyn_raw{0};
  int lh_n{0};
};

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
  float conf = 0.0f;
  const std::uint8_t n = std::min<std::uint8_t>(lh.m_hostline_num, 4);
  for (std::uint8_t i = 0; i < n; ++i) {
    const auto& line = lh.m_hostline[i];
    if (line.m_LH_Confidence < 0.1f && line.m_LH_Availability_State == 0) {
      continue;
    }
    conf = std::max(conf, line.m_LH_Confidence);
    // Same as Host _fcm_style_perc: use published VR, else 60. Do not invent 20 m.
    const float x1 = (line.m_LH_First_VR_End > 0.5f) ? line.m_LH_First_VR_End : 60.0f;
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
  g.conf = g.valid ? std::max(conf, 0.20f) : 0.0f;
  // Host lane_count = driving lanes. FCM has no that field: 1 + adj present.
  g.lane_count = 1.0f;
  if (g.valid && perc.Perception_LA_Out.m_adj_line_num >= 1) {
    g.lane_count = 2.0f;
  }
  return g;
}

bool ObjAlreadyPacked(const oct_gen::PlanObj* obj, int n, float d, float lat) {
  for (int i = 0; i < n; ++i) {
    if (std::fabs(obj[i].d - d) < 1.5f && std::fabs(obj[i].lat - lat) < 0.8f) {
      return true;
    }
  }
  return false;
}

template <typename ObjT>
void TryPushObj(PercView& v, const ObjT& o) {
  if (v.nobj >= oct_gen::kObjNMax) {
    return;
  }
  if (o.m_OBJ_ID == 0 || o.m_OBJ_Long_Distance < 0.0f || o.m_OBJ_Long_Distance > kObjDMaxM) {
    return;
  }
  const float d = o.m_OBJ_Long_Distance;
  const float lat = o.m_OBJ_Lat_Distance;
  if (ObjAlreadyPacked(v.obj, v.nobj, d, lat)) {
    return;
  }
  oct_gen::PlanObj row{};
  row.d = d;
  row.rel = o.m_OBJ_Relative_Long_Velocity;
  row.lat = lat;
  row.len_m = std::max(o.m_OBJ_Length, 0.5f);
  row.cls = static_cast<float>(o.m_OBJ_Object_Class);
  row.heading = o.m_OBJ_Heading;  // radians, same as Host heading_rad
  row.is_ped = (static_cast<int>(o.m_OBJ_Object_Class) == 5) ? 1.0f : 0.0f;
  v.obj[v.nobj++] = row;
}

// One walk of dyn[] + one walk of hostlines. Empty → nobj=0 (Host _pack_obj []).
// CIPV first, then the rest. Do not LeadFromPerc then pack again.
PercView ExtractPerc(const gf_gen::Perception_MESSAGE_Out_St& perc) {
  PercView v{};
  v.lane = HostLaneFromPerc(perc);
  const auto& dyn = perc.Perception_DYN_OBJ_Out;
  v.dyn_raw = static_cast<int>(dyn.m_OBJ_VD_Count) + static_cast<int>(dyn.m_OBJ_Ped_Count);
  v.lh_n = static_cast<int>(perc.Perception_LH_Out.m_hostline_num);
  const int n_src = std::min(kDynCap, std::max(v.dyn_raw, static_cast<int>(dyn.m_OBJ_VD_Count)));
  if (dyn.m_OBJ_VD_CIPV_ID != 0) {
    for (int i = 0; i < n_src; ++i) {
      if (dyn.m_Obj_item[i].m_OBJ_ID == dyn.m_OBJ_VD_CIPV_ID) {
        TryPushObj(v, dyn.m_Obj_item[i]);
        break;
      }
    }
  }
  for (int i = 0; i < n_src; ++i) {
    TryPushObj(v, dyn.m_Obj_item[i]);
  }
  const auto& st = perc.Perception_STATIC_OBJ_Out;
  const int n_st = std::min(10, static_cast<int>(st.m_Static_OBJ_Count));
  for (int i = 0; i < n_st; ++i) {
    const auto& o = st.m_Obj_item[i];
    if (o.m_OBJ_ID == 0 || o.m_OBJ_Long_Distance < 0.0f ||
        o.m_OBJ_Long_Distance > kObjDMaxM) {
      continue;
    }
    if (ObjAlreadyPacked(v.obj, v.nobj, o.m_OBJ_Long_Distance, o.m_OBJ_Lat_Distance)) {
      continue;
    }
    if (v.nobj >= oct_gen::kObjNMax) {
      break;
    }
    oct_gen::PlanObj row{};
    row.d = o.m_OBJ_Long_Distance;
    row.rel = 0.0f;
    row.lat = o.m_OBJ_Lat_Distance;
    row.len_m = std::max(o.m_OBJ_Length, 0.5f);
    row.cls = static_cast<float>(o.m_OBJ_Object_Class);
    row.heading = o.m_OBJ_Heading;
    row.is_ped = (static_cast<int>(o.m_OBJ_Object_Class) == 5) ? 1.0f : 0.0f;
    v.obj[v.nobj++] = row;
  }
  const auto& tsr = perc.Perception_DSTSR_Out;
  const int n_tsr = std::min(6, static_cast<int>(tsr.m_tsr_num));
  for (int i = 0; i < n_tsr; ++i) {
    const auto& it = tsr.m_TSR_Item[i];
    const int name = static_cast<int>(it.m_DSTSR_Sign_Name);
    // e_trafficSignals=164, e_stopAhead=196 — phantom stop, no new .m I/O.
    if (name != 164 && name != 196) {
      continue;
    }
    const float d = it.m_DSTSR_Sign_Long_Distance;
    const float lat = it.m_DSTSR_Sign_Lat_Distance;
    if (d < 0.0f || d > kObjDMaxM) {
      continue;
    }
    if (ObjAlreadyPacked(v.obj, v.nobj, d, lat) || v.nobj >= oct_gen::kObjNMax) {
      continue;
    }
    oct_gen::PlanObj row{};
    row.d = d;
    row.rel = 0.0f;
    row.lat = lat;
    row.len_m = 1.0f;
    row.cls = 1.0f;
    row.heading = 0.0f;
    row.is_ped = 0.0f;
    v.obj[v.nobj++] = row;
  }
  return v;
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
  return 0;
}

std::uint64_t now_ns() {
  return static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(
          std::chrono::steady_clock::now().time_since_epoch())
          .count());
}

void ApplyTick(const oct_gen::PlanTickOut& tick, const gf_gen::EgoMotion& ego,
               gf_gen::Trajectory& traj) {
  traj.point_count = static_cast<std::uint8_t>(oct_gen::kLatTrajPoints);
  traj.gear_shift_first = ego.gear;
  traj.gear_shift_second = 0;
  for (int i = 0; i < oct_gen::kLatTrajPoints; ++i) {
    traj.points_x_m[i] = tick.path.x_m[i];
    traj.points_y_m[i] = tick.path.y_m[i];
    traj.points_v_mps[i] = tick.path.v_mps[i];
  }
  traj.throttle = tick.throttle;
  traj.brake = tick.brake;
  traj.steer = tick.steer;
  traj.target_speed_mps = tick.target_speed_mps;
  traj.ctrl_mode = CtrlModeId(tick.mode);
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

  std::optional<gf_gen::EgoMotion> last_ego;
  std::optional<gf_gen::Perception_MESSAGE_Out_St> last_perc;
  float D_see_prev = 0.0f;
  float T_plan_prev = 0.0f;
  std::uint64_t seq = 0;
  const int log_every = LogEvery();
  const char* last_log_mode = "";
  int last_log_nobj = -1;
  int last_log_lane = -1;
  int last_log_lh = -1;
  float last_log_ey = 0.0f;
  float last_log_dsee = 0.0f;
  float last_log_areq = 0.0f;
  float last_log_thr = 0.0f;
  float last_log_brk = 0.0f;
  float last_log_st = 0.0f;
  gf_app::EnsureDiagLogSinks();
  gf_app::FrameWatch rx_ego;
  gf_app::FrameWatch rx_perc;
  gf_app::FrameWatch tx_traj;
  rx_ego.Init("plan", "rx.ego");
  rx_ego.BindService("EgoMotion");
  rx_perc.Init("plan", "rx.perc");
  rx_perc.BindService("Perception_MESSAGE_Out_St");
  rx_perc.BindCameraCeiling();
  tx_traj.Init("plan", "tx.traj");
  tx_traj.BindService("Trajectory");
  std::uint64_t last_perc_ts = 0;
  bool have_planned = false;

  std::cout << "gf-planning-driving: start (v4 m_plan_tick; perc-triggered; ego cached"
            << "; stdout=on-change+/" << log_every
            << "; frame_watch=identity+budget perc[" << rx_perc.PolicyHint()
            << "] ego[" << rx_ego.PolicyHint() << "])\n";

  while (!iox::posix::hasTerminationRequested()) {
    supervisor.Tick();
    if (supervisor.ExitForEmRestart()) {
      return gf_ara::exec::kEmRestartExitCode;
    }

    if (auto t = ego_sub.Take(); t && t.Value().has_value()) {
      last_ego = *t.Value();
      rx_ego.Observe(0, last_ego->timestamp_ns, false, true);
    }
    if (auto t = perc_sub.Take(); t && t.Value().has_value()) {
      last_perc = *t.Value();
    }

    if (!last_perc || !last_ego) {
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
      continue;
    }

    const auto& ego = *last_ego;
    const std::uint64_t perc_ts =
        last_perc->Perception_DYN_OBJ_Out.m_time_stamp * 1000ULL;
    rx_perc.Observe(0, perc_ts, false, true);
    if (have_planned && perc_ts == last_perc_ts) {
      last_perc.reset();
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
      continue;
    }
    const auto t0 = std::chrono::steady_clock::now();
    const PercView view = ExtractPerc(*last_perc);
    last_perc.reset();
    const auto tick = oct_gen::m_plan_tick(
        ego.speed_mps, ego.steer_angle_deg, view.lane.valid, view.lane.e_y, view.lane.c0,
        view.lane.c1, view.lane.c2, view.lane.c3, view.lane.x_end, view.lane.conf,
        view.lane.lane_count, view.nobj ? view.obj : nullptr, view.nobj, D_see_prev, T_plan_prev);
    D_see_prev = tick.D_see;
    T_plan_prev = tick.T_plan;

    gf_gen::Trajectory traj{};
    ApplyTick(tick, ego, traj);
    traj.timestamp_ns = now_ns();
    const auto tick_ms = std::chrono::duration<double, std::milli>(
                             std::chrono::steady_clock::now() - t0)
                             .count();

    if (static_cast<bool>(traj_pub.Send(traj))) {
      tx_traj.Observe(seq, traj.timestamp_ns);
      last_perc_ts = perc_ts;
      have_planned = true;
      const int lane_ok = view.lane.valid ? 1 : 0;
      const bool changed =
          std::strcmp(tick.mode, last_log_mode) != 0 || view.nobj != last_log_nobj ||
          lane_ok != last_log_lane || view.lh_n != last_log_lh ||
          FMoved(view.lane.e_y, last_log_ey, 0.25f) ||
          FMoved(tick.D_see, last_log_dsee, 0.5f) ||
          FMoved(tick.a_req, last_log_areq, 0.2f) ||
          FMoved(traj.throttle, last_log_thr, 0.02f) ||
          FMoved(traj.brake, last_log_brk, 0.02f) ||
          FMoved(traj.steer, last_log_st, 0.02f);
      if (log_every <= 1 || changed ||
          (seq % static_cast<std::uint64_t>(log_every) == 0)) {
        std::cout << "[perf][planning] tick_ms=" << tick_ms << " seq=" << seq
                  << " pts=" << static_cast<int>(traj.point_count)
                  << " y_end=" << traj.points_y_m[traj.point_count - 1]
                  << " e_y=" << view.lane.e_y << " lh=" << view.lh_n
                  << " lane=" << lane_ok << " dyn=" << view.dyn_raw
                  << " nobj=" << view.nobj << " mode=" << tick.mode
                  << " D_see=" << tick.D_see << " a_req=" << tick.a_req
                  << " thr=" << traj.throttle << " brk=" << traj.brake
                  << " st=" << traj.steer << std::endl;
        last_log_mode = tick.mode;
        last_log_nobj = view.nobj;
        last_log_lane = lane_ok;
        last_log_lh = view.lh_n;
        last_log_ey = view.lane.e_y;
        last_log_dsee = tick.D_see;
        last_log_areq = tick.a_req;
        last_log_thr = traj.throttle;
        last_log_brk = traj.brake;
        last_log_st = traj.steer;
      }
      ++seq;
    }
  }
  return EXIT_SUCCESS;
}
