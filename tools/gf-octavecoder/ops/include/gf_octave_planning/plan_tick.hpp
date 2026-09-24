#pragma once

#include "gf_octave_planning/lat_follow.hpp"
#include "gf_octave_planning/lat_host_delta.hpp"
#include "gf_octave_planning/lat_traj.hpp"
#include "gf_octave_planning/lc_path.hpp"
#include "gf_octave_planning/lon_acc_aeb.hpp"
#include "gf_octave_planning/plan_obj.hpp"

#include <algorithm>
#include <cmath>

// 1:1 octave_planning/afc/m_plan.m + m_ctrl.m + m_plan_tick.m
// Plan: path, v(s), a_req, target. Ctrl: track + residuals. No mixed laws.
// Idle and post-reg: same host-keep δ. Cool only blocks re-enter.
// S-corridor before reg. Remap is pose only. Hold enter snaps last to δ_ff. Ctrl only follows.

namespace gf_octave_planning {

struct PlanTickOut {
  float throttle{0.0f};
  float brake{0.0f};
  float steer{0.0f};
  float target_speed_mps{25.0f};
  const char* mode{"cruise"};
  float D_see{120.0f};
  float T_plan{10.0f};
  float D_occ{120.0f};
  float a_req{0.0f};
  float horizon_m{25.0f};
  float allow_lc{0.0f};
  float lc_s_done{0.0f};
  float lc_L{0.0f};
  float s_stop{120.0f};
  float delta_ff{0.0f};
  float psi{0.0f};
  int target{0};
  float err_delta{0.0f};
  float err_v{0.0f};
  float err_e{0.0f};
  float err_epsi{0.0f};
  float y_dr{0.0f};
  float y_s{0.0f};
  float y_road{0.0f};
  int remapped{0};
  int paint_ok{0};
  float commit_m{0.0f};
  int reg{0};
  int plant_n{0};
  LatTraj path{};
};

struct PlanOnly {
  LatTraj path{};
  float D_see{120.0f};
  float T_plan{10.0f};
  float D_occ{120.0f};
  float a_req{0.0f};
  float horizon_m{25.0f};
  float s_stop{120.0f};
  float v_plan{0.0f};
  float allow_lc{0.0f};
  float lc_s_done{0.0f};
  float lc_L{0.0f};
  float delta_ff{0.0f};
  float e{0.0f};
  float epsi{0.0f};
  float y_dr{0.0f};
  float y_s{0.0f};
  float y_road{0.0f};
  int remapped{0};
  int paint_ok{0};
  float commit_m{0.0f};
  int reg{0};
  int plant_n{0};
  float psi{0.0f};
  int target{0};
  bool lane_ok{true};
};

inline int& plan_cool() {
  static int s = 0;
  return s;
}


inline PlanOnly m_plan(float v, float steer_deg, bool lane_valid, float e_y, float c0, float c1,
                       float c2, float c3, float x_end, const PlanObj* obj, int nobj,
                       float D_see_prev, float T_plan_prev, float v_sign_max, float v_sign_min,
                       int lc_side, float d_f, float d_r, float rel_r, float dt, float d_hard,
                       float rel_f = 0.0f, float hdg_f = 0.0f, bool paint_ok = false,
                       bool land_ok = true) {
  const PlanCal& p = plan_cal();
  PlanOnly plan{};
  v = std::max(0.0f, v);
  if (dt <= 0.0f) {
    dt = p.plan_dt_s;
  }
  nobj = clamp_nobj(nobj);
  if (nobj < 1) {
    obj = nullptr;
  }

  plan.D_occ = plan_occlusion(obj, nobj, c0);
  const float D_fov = plan_d_fov(c0, c1, c2, c3, x_end);
  const PlanHorizon hz =
      plan_horizon(v, lane_valid, e_y, c1, x_end, plan.D_occ, D_fov, D_see_prev, T_plan_prev);

  int side_in = lc_side;
  if (plan_cool() != 0) {
    side_in = 0;
  }
  const LcPathOut lc =
      m_lc_path(side_in, v, d_f, d_r, rel_r, dt, steer_deg, d_hard, rel_f, hdg_f, e_y, c1,
                paint_ok, c2, c3, land_ok);
  const bool follow = lc.hold.active != 0;
  const float host_d = gf_lat_host_delta(lane_valid, e_y, c1, c2, c3, v);
  if (follow) {
    plan.path = lc.path;
    plan.D_see = std::min({p.d_cal_cap_m, std::max(d_f, 0.5f), std::max(d_hard, 0.5f)});
    plan.T_plan = std::max(p.t_plan_min_s, plan.D_see / std::max(v, p.traj_speed_floor_mps));
    plan.lane_ok = true;
    plan_cool() = 0;
  } else {
    plan.D_see = hz.D_see;
    plan.T_plan = hz.T_plan;
    plan.path = m_lat_traj(v, plan.D_see, plan.T_plan, lane_valid, c0, c1, c2, c3, x_end);
    plan.lane_ok = lane_usable(lane_valid, e_y, c1);
    if (std::fabs(e_y) > p.lat_ey_slow_m) {
      plan.lane_ok = false;
    }
    if (lc.hold.done != 0 || lc.hold.aborted != 0) {
      plan_cool() = p.lc_cool_n;
    }
    if (plan_cool() != 0) {
      plan_cool() -= 1;
    }
  }

  const int npts = std::min(kLatTrajPoints, std::max(2, p.traj_n));
  plan.s_stop = plan_reg_stop(obj, nobj, c0);
  const PlanObj* lon_obj = follow ? nullptr : obj;
  const int lon_n = follow ? 0 : nobj;
  plan_speed_profile(plan.path.x_m, npts, v, lon_obj, lon_n, plan.D_see, plan.lane_ok,
                     plan.path.v_mps, c0, plan.s_stop, v_sign_max, v_sign_min);
  plan.v_plan = plan.path.v_mps[0];
  float a_req = lon_a_req_n(v, lon_obj, lon_n, c0);
  if (plan.D_see < p.d_vis_tight_m) {
    const float a_max = std::max(p.aeb_decel_mps2, 0.5f);
    a_req = std::min(a_max, a_req * p.a_req_vis_gain);
  }
  const float a_reg = lon_a_req_stop(v, plan.s_stop);
  if (a_reg > a_req) {
    a_req = a_reg;
  }
  if (follow) {
    const float d_need = (v * v) / (2.0f * std::max(p.lc_a_plan_mps2, 0.5f));
    if (d_need > plan.D_see) {
      const float a_s = (v * v) / (2.0f * std::max(plan.D_see, 1.0f));
      a_req = std::max(a_req, std::min(a_s, std::max(p.aeb_decel_mps2, 0.5f)));
    }
  }
  if (!plan.lane_ok) {
    for (int i = 0; i < npts; ++i) {
      plan.path.v_mps[i] = 0.0f;
    }
    plan.v_plan = 0.0f;
  }
  plan.a_req = a_req;
  plan.horizon_m = plan.path.horizon_m;
  plan.allow_lc = follow ? 1.0f : 0.0f;
  plan.lc_s_done = lc.hold.s_done;
  plan.lc_L = lc.hold.L;
  plan.delta_ff = follow ? lc.hold.delta_ff : host_d;
  plan.commit_m = 0.0f;
  plan.reg = lc.hold.reg;
  plan.plant_n = lc.hold.plant_n;
  plan.e = lc.hold.e;
  plan.epsi = lc.hold.epsi;
  plan.y_dr = lc.hold.y;
  plan.y_s = lc.hold.y_s;
  plan.y_road = lc.hold.y_road;
  plan.remapped = lc.hold.remapped;
  plan.paint_ok = lc.hold.paint_ok;
  plan.psi = lc.hold.psi;
  plan.target = follow ? 1 : 0;
  return plan;
}

inline int& ctrl_prev_tgt() {
  static int t = 0;
  return t;
}

inline PlanTickOut m_ctrl(const PlanOnly& plan, float v, float steer_deg, bool lane_valid,
                          float e_y, float c1) {
  (void)lane_valid;
  (void)e_y;
  (void)c1;
  PlanTickOut out{};
  v = std::max(0.0f, v);
  const LonCtrl lon = lon_exec(v, plan.v_plan, plan.a_req);
  if (plan.target == 1 && ctrl_prev_tgt() != 1) {
    lat_cmd_last() = plan.delta_ff;
  }
  out.steer = m_lat_follow(plan.delta_ff, steer_deg);
  ctrl_prev_tgt() = plan.target;
  const float ego_rad = steer_deg * 3.14159265f / 180.0f;
  out.throttle = lon.throttle;
  out.brake = lon.brake;
  out.mode = lon.mode;
  out.target_speed_mps = lon.target_speed_mps;
  out.err_delta = ego_rad - plan.delta_ff;
  out.err_v = v - plan.v_plan;
  out.err_e = plan.e;
  out.err_epsi = plan.epsi;
  out.y_dr = plan.y_dr;
  out.y_s = plan.y_s;
  out.y_road = plan.y_road;
  out.remapped = plan.remapped;
  out.paint_ok = plan.paint_ok;
  out.commit_m = plan.commit_m;
  out.reg = plan.reg;
  out.plant_n = plan.plant_n;
  return out;
}

inline PlanTickOut m_plan_tick(float v, float steer_deg, bool lane_valid, float e_y, float c0,
                               float c1, float c2, float c3, float x_end, float lane_conf,
                               float lane_count, const PlanObj* obj, int nobj, float D_see_prev,
                               float T_plan_prev, float v_sign_max = 1.0e6f,
                               float v_sign_min = 0.0f, int lc_side = 0, float d_f = 0.0f,
                               float d_r = 0.0f, float rel_r = 0.0f, float dt = 0.0f,
                               float d_hard = 1.0e6f, float rel_f = 0.0f, float hdg_f = 0.0f,
                               bool paint_ok = false, bool land_ok = true) {
  (void)lane_conf;
  (void)lane_count;
  const PlanOnly plan =
      m_plan(v, steer_deg, lane_valid, e_y, c0, c1, c2, c3, x_end, obj, nobj, D_see_prev,
             T_plan_prev, v_sign_max, v_sign_min, lc_side, d_f, d_r, rel_r, dt, d_hard, rel_f,
             hdg_f, paint_ok, land_ok);
  PlanTickOut out = m_ctrl(plan, v, steer_deg, lane_valid, e_y, c1);
  out.D_see = plan.D_see;
  out.T_plan = plan.T_plan;
  out.D_occ = plan.D_occ;
  out.a_req = plan.a_req;
  out.horizon_m = plan.horizon_m;
  out.s_stop = plan.s_stop;
  out.path = plan.path;
  out.allow_lc = plan.allow_lc;
  out.lc_s_done = plan.lc_s_done;
  out.lc_L = plan.lc_L;
  out.delta_ff = plan.delta_ff;
  out.psi = plan.psi;
  out.target = plan.target;
  out.commit_m = plan.commit_m;
  out.reg = plan.reg;
  out.plant_n = plan.plant_n;
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
