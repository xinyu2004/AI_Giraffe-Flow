#pragma once

#include "gf_octave_planning/lat_lka.hpp"
#include "gf_octave_planning/lat_traj.hpp"
#include "gf_octave_planning/lon_acc_aeb.hpp"
#include "gf_octave_planning/plan_obj.hpp"

#include <algorithm>
#include <cmath>

// 1:1 octave_planning/afc/m_plan_tick.m — one call per perc tick.

namespace gf_octave_planning {

struct PlanTickOut {
  float throttle{0.0f};
  float brake{0.0f};
  float steer{0.0f};
  float target_speed_mps{12.0f};
  const char* mode{"cruise"};
  float D_see{120.0f};
  float T_plan{10.0f};
  float D_occ{120.0f};
  float a_req{0.0f};
  float horizon_m{25.0f};
  float allow_lc{0.0f};
  LatTraj path{};
};

inline PlanTickOut m_plan_tick(float v, float steer_deg, bool lane_valid, float e_y, float c0,
                               float c1, float c2, float c3, float x_end, float lane_conf,
                               float lane_count, const PlanObj* obj, int nobj, float D_see_prev,
                               float T_plan_prev) {
  const PlanCal& p = plan_cal();
  PlanTickOut out{};
  v = std::max(0.0f, v);
  nobj = clamp_nobj(nobj);
  if (nobj < 1) {
    obj = nullptr;
  }

  const float D_fov = p.d_fov_conf_m * clamp(lane_conf, p.d_fov_conf_min, 1.0f);
  out.D_occ = plan_occlusion(obj, nobj);
  const PlanHorizon hz =
      plan_horizon(v, lane_valid, e_y, c1, x_end, out.D_occ, D_fov, D_see_prev, T_plan_prev);
  out.D_see = hz.D_see;
  out.T_plan = hz.T_plan;

  bool lane_ok = lane_usable(lane_valid, e_y, c1);
  if (std::fabs(e_y) > p.lat_ey_slow_m) {
    lane_ok = false;
  }

  out.path = m_lat_traj(v, out.D_see, out.T_plan, lane_valid, c0, c1, c2, c3, x_end);
  const int npts = std::min(kLatTrajPoints, std::max(2, p.traj_n));
  plan_speed_profile(out.path.x_m, npts, v, obj, nobj, out.D_see, lane_ok, out.path.v_mps);
  const float v_plan = out.path.v_mps[0];
  float a_req = lon_a_req_n(v, obj, nobj);
  if (out.D_see < p.d_vis_tight_m) {
    const float a_max = std::max(p.aeb_decel_mps2, 0.5f);
    a_req = std::min(a_max, a_req * p.a_req_vis_gain);
  }
  if (!lane_ok) {
    for (int i = 0; i < npts; ++i) {
      out.path.v_mps[i] = 0.0f;
    }
  }
  out.a_req = a_req;
  out.horizon_m = out.path.horizon_m;
  const LonCtrl ctrl = lon_exec(v, lane_ok ? v_plan : 0.0f, a_req);
  out.throttle = ctrl.throttle;
  out.brake = ctrl.brake;
  out.target_speed_mps = ctrl.target_speed_mps;
  out.mode = ctrl.mode;
  out.steer = m_lat_lka(lane_valid, e_y, c1, steer_deg);

  out.allow_lc = 0.0f;
  if (lane_ok && lane_count >= 2.0f && out.T_plan >= p.t_lc_min_s && out.D_see >= p.d_lc_min_m &&
      lane_conf >= p.lc_conf_min) {
    out.allow_lc = 1.0f;
  }
  return out;
}

// 1:1 m_lon_acc_aeb.m — single-lead row into m_plan_tick (no second lon path).
inline LonCtrl m_lon_acc_aeb(float v, bool lead_valid, float d, float rel, float lead_lat_m = 0.0f,
                             float e_y = 0.0f, float c1 = 0.0f, bool lane_valid = true) {
  PlanObj one{};
  int n = 0;
  if (lead_valid) {
    one.d = d;
    one.rel = rel;
    one.lat = lead_lat_m;
    one.len_m = 4.5f;
    one.cls = 1.0f;
    n = 1;
  }
  const PlanTickOut o = m_plan_tick(v, 0.0f, lane_valid, e_y, e_y, c1, 0.0f, 0.0f, 1.0e6f, 1.0f,
                                    1.0f, n ? &one : nullptr, n, 0.0f, 0.0f);
  LonCtrl c{};
  c.throttle = o.throttle;
  c.brake = o.brake;
  c.target_speed_mps = o.target_speed_mps;
  c.mode = o.mode;
  return c;
}

}  // namespace gf_octave_planning
