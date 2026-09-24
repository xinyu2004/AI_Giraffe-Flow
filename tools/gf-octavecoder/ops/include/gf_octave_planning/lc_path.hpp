#pragma once

#include "gf_octave_planning/clamp.hpp"
#include "gf_octave_planning/lat_host_delta.hpp"
#include "gf_octave_planning/lat_traj.hpp"
#include "gf_octave_planning/lc_pose.hpp"
#include "gf_octave_planning/lc_side.hpp"
#include "gf_octave_planning/plan_cal.hpp"

#include <algorithm>
#include <cmath>

// 1:1 octave_planning/afc/m_lc_path.m — committed S then new-host.
// Pose: paint when geom; DR increment only while paint gone.
// Remap = FCM host jumped (pose). Reg = law switch, only in the new band.
// Before reg: S-curve, s monotonic, hold_ok + land_ok can abort.
// After reg: same host-keep as idle; path = m_lat_traj (not y=e·t). No abort.
// Done is dwell bookkeeping, not a law switch. Cool is m_plan. AFC never calls.

namespace gf_octave_planning {

struct LcPathHold {
  int active{0};
  int done{0};
  int aborted{0};
  float s_done{0.0f};
  float L{0.0f};
  int side{0};
  float delta_ff{0.0f};
  float psi{0.0f};
  float kappa{0.0f};
  float e{0.0f};
  float epsi{0.0f};
  float y{0.0f};
  float y_s{0.0f};
  float y_road{0.0f};
  int remapped{0};
  int paint_ok{0};
  int reg{0};
  int plant_n{0};
};

struct LcPathOut {
  LatTraj path{};
  LcPathHold hold{};
};

struct LcPathSt {
  int active{0};
  int side{0};
  float L{0.0f};
  float W{0.0f};
  float s{0.0f};
  float x{0.0f};
  float y{0.0f};
  float psi{0.0f};
  int plant_n{0};
  int reg{0};
  float reg_d{0.0f};
  LcPose pose{};
};

inline LcPathSt& lc_path_st() {
  static LcPathSt s{};
  return s;
}

inline void m_lc_path_reset() {
  lc_path_st() = LcPathSt{};
}

inline float lc_sigma(float u) {
  u = std::min(1.0f, std::max(0.0f, u));
  const float u2 = u * u;
  const float u3 = u2 * u;
  return 10.0f * u3 - 15.0f * u2 * u2 + 6.0f * u3 * u2;
}

inline float lc_sigma_inv(float s) {
  s = std::min(1.0f, std::max(0.0f, s));
  float lo = 0.0f;
  float hi = 1.0f;
  for (int k = 0; k < 20; ++k) {
    const float mid = 0.5f * (lo + hi);
    if (lc_sigma(mid) < s) {
      lo = mid;
    } else {
      hi = mid;
    }
  }
  return 0.5f * (lo + hi);
}

inline void lc_corridor(float W, float lw, float* ylo, float* yhi) {
  const float half = 0.5f * std::max(lw, 1.0f);
  if (W >= 0.0f) {
    *ylo = -half;
    *yhi = W + half;
  } else {
    *yhi = half;
    *ylo = W - half;
  }
}

inline bool lc_in_target(float y, float W, float lw, float ylo, float yhi) {
  const float pad = 0.30f;
  const float line = 0.5f * std::max(lw, 1.0f);
  if (W >= 0.0f) {
    return y >= line - 0.20f && y <= yhi - pad;
  }
  return y <= -line + 0.20f && y >= ylo + pad;
}

inline float lc_delta_in_band(float d_s, float y, float W, float lw, float ylo, float yhi,
                              int across = 0) {
  const float pad = 0.30f;
  const float line = 0.5f * std::max(lw, 1.0f);
  float d = d_s;
  if (across == 0) {
    if (W >= 0.0f) {
      if (y < line + pad) {
        d = std::min(d, 0.0f);
      }
    } else if (y > -line - pad) {
      d = std::max(d, 0.0f);
    }
  }
  if (y > yhi - pad) {
    d = std::max(d, 0.04f * (y - (yhi - pad)));
  } else if (y < ylo + pad) {
    d = std::min(d, -0.04f * ((ylo + pad) - y));
  }
  return d;
}

inline float lc_progress_s(float x, float y, float L, float W, float lw) {
  L = std::max(L, 1.0e-3f);
  const float u_x = std::min(1.0f, std::max(0.0f, x / L));
  if (std::fabs(W) < 1.0e-3f) {
    return std::min(std::max(0.0f, x), L);
  }
  float lat = y / W;
  lat = std::min(1.0f, std::max(0.0f, lat));
  const float u_y = lc_sigma_inv(lat);
  const float u_rise = 0.25f;
  const float line = 0.5f * std::max(lw, 1.0f);
  float u = 0.0f;
  if (std::fabs(y) < line + 0.30f) {
    u = std::min(u_x, std::min(std::max(u_rise, u_y), 0.5f));
  } else if (u_y < 0.5f) {
    u = std::min(u_x, std::max(u_rise, u_y));
  } else {
    u = std::min(u_x, u_y);
  }
  return u * L;
}

inline void lc_geom(float s, float L, float W, float wb, float* psi, float* kappa, float* delta) {
  L = std::max(L, 1.0e-3f);
  const float u = std::min(1.0f, std::max(0.0f, s / L));
  const float om = 1.0f - u;
  const float sigp = 30.0f * u * u * om * om;
  const float sigpp = 60.0f * u * om * (1.0f - 2.0f * u);
  const float yp = (W / L) * sigp;
  const float ypp = (W / (L * L)) * sigpp;
  const float ps = std::atan(yp);
  const float kap = ypp / std::pow(1.0f + yp * yp, 1.5f);
  const float del = -std::atan(wb * kap);
  if (psi) {
    *psi = ps;
  }
  if (kappa) {
    *kappa = kap;
  }
  if (delta) {
    *delta = del;
  }
}

inline LcPathHold hold_from_st(const LcPathSt& st) {
  LcPathHold h{};
  h.s_done = st.s;
  h.L = st.L;
  h.side = st.side;
  h.y = st.y;
  return h;
}

inline void lc_dead_reckon(LcPathSt& st, float v, float dt, float steer_deg, float wb) {
  wb = std::max(wb, 0.5f);
  const float delta = steer_deg * 3.14159265f / 180.0f;
  const float kap = -std::tan(delta) / wb;
  st.psi = st.psi + v * kap * dt;
  st.x = st.x + v * std::cos(st.psi) * dt;
  st.y = st.y + v * std::sin(st.psi) * dt;
}

inline LcPathOut m_lc_path(int lc_side, float v, float d_f, float d_r, float rel_r, float dt,
                           float steer_deg = 0.0f, float d_hard = 1.0e6f, float rel_f = 0.0f,
                           float hdg_f = 0.0f, float e_y = 0.0f, float c1 = 0.0f,
                           bool paint_ok = false, float c2 = 0.0f, float c3 = 0.0f,
                           bool land_ok = true) {
  const PlanCal& p = plan_cal();
  LcPathSt& st = lc_path_st();
  if (dt <= 0.0f) {
    dt = p.plan_dt_s;
  }
  dt = clamp(dt, p.lc_dt_min_s, p.lc_dt_max_s);
  v = std::max(0.0f, v);
  int side = 0;
  if (lc_side > 0) {
    side = 1;
  } else if (lc_side < 0) {
    side = -1;
  }

  LcPathOut out{};
  out.hold = hold_from_st(st);
  const int n = std::min(kLatTrajPoints, std::max(2, p.traj_n));

  if (side == 0) {
    st = LcPathSt{};
    return out;
  }
  if (st.active != 0) {
    side = st.side;
  }

  if (st.active == 0) {
    const float L = gf_lc_L_need();
    if (!gf_lc_can(true, d_f, d_r, rel_r, v, 0.0f, d_hard, rel_f, hdg_f)) {
      return out;
    }
    st.active = 1;
    st.side = side;
    st.L = L;
    st.W = static_cast<float>(side) * p.lane_width_m;
    st.s = 0.0f;
    st.x = 0.0f;
    st.y = 0.0f;
    st.psi = 0.0f;
    st.plant_n = 0;
    st.reg = 0;
    st.reg_d = 0.0f;
    st.pose = gf_lc_pose_zero();
  }

  lc_dead_reckon(st, v, dt, steer_deg, p.wheelbase_m);
  st.pose = gf_lc_pose(st.pose, e_y, c1, paint_ok, st.W, st.y, st.psi);
  const float y_use = st.pose.y;
  const float psi_use = st.pose.psi;
  if (st.reg == 0) {
    if (!land_ok || !gf_lc_hold_ok(d_f, d_r, rel_r, v, d_hard, rel_f, hdg_f)) {
      out.hold = hold_from_st(st);
      out.hold.aborted = 1;
      out.hold.active = 0;
      st = LcPathSt{};
      return out;
    }
  }
  float ylo = 0.0f;
  float yhi = 0.0f;
  lc_corridor(st.W, p.lane_width_m, &ylo, &yhi);
  float s_raw = 0.0f;
  if (st.reg != 0) {
    s_raw = st.s;
  } else {
    s_raw = lc_progress_s(st.x, y_use, st.L, st.W, p.lane_width_m);
  }
  st.s = std::max(st.s, s_raw);
  float psi_s = 0.0f;
  float k_s = 0.0f;
  float d_s = 0.0f;
  lc_geom(st.s, st.L, st.W, p.wheelbase_m, &psi_s, &k_s, &d_s);
  float y_s = 0.0f;
  if (st.reg == 0 && st.pose.remapped != 0) {
    bool in_band = std::fabs(e_y) < p.lc_settle_ey_m;
    if (!in_band && st.s + 1.0e-3f >= st.L) {
      in_band = lc_in_target(y_use, st.W, p.lane_width_m, ylo, yhi);
    }
    if (in_band) {
      st.reg_d = d_s;
      st.reg = 1;
    }
  }
  if (st.reg != 0) {
    if (paint_ok) {
      d_s = gf_lat_host_delta(true, e_y, c1, c2, c3, v);
    } else {
      d_s = st.reg_d;
    }
    d_s = lc_delta_in_band(d_s, y_use, st.W, p.lane_width_m, ylo, yhi, 1);
    st.reg_d = d_s;
    psi_s = 0.0f;
    k_s = 0.0f;
    y_s = st.W;
    out.hold.e = e_y;
    out.hold.epsi = psi_use;
  } else {
    d_s = lc_delta_in_band(d_s, y_use, st.W, p.lane_width_m, ylo, yhi, 0);
    y_s = clamp(st.W * lc_sigma(st.s / std::max(st.L, 1.0e-3f)), ylo, yhi);
    const float dx = st.x - st.s;
    const float dy = y_use - y_s;
    out.hold.e = -dx * std::sin(psi_s) + dy * std::cos(psi_s);
    out.hold.epsi = psi_use - psi_s;
  }
  out.hold.s_done = st.s;
  out.hold.L = st.L;
  out.hold.side = st.side;
  out.hold.psi = psi_s;
  out.hold.kappa = k_s;
  out.hold.delta_ff = d_s;
  out.hold.y = st.y;
  out.hold.y_s = y_s;
  out.hold.y_road = y_use;
  out.hold.remapped = st.pose.remapped;
  out.hold.paint_ok = st.pose.paint_ok;
  out.hold.reg = st.reg;
  const float psi_lim = p.lc_settle_steer_deg * 3.14159265f / 180.0f;
  bool in_tgt = false;
  float psi_done = st.psi;
  if (paint_ok) {
    psi_done = psi_use;
    if (st.pose.remapped != 0) {
      in_tgt = std::fabs(e_y) < p.lc_settle_ey_m;
    } else {
      in_tgt = lc_in_target(y_use, st.W, p.lane_width_m, ylo, yhi);
    }
  } else {
    in_tgt = lc_in_target(st.y, st.W, p.lane_width_m, ylo, yhi);
  }
  const float d_deg = d_s * 180.0f / 3.14159265f;
  const bool d_lim = std::fabs(d_deg) < p.lc_settle_steer_deg;
  const bool trk_lim = std::fabs(steer_deg - d_deg) < p.lc_settle_steer_deg;
  const bool planted = in_tgt && std::fabs(psi_done) < psi_lim &&
                       std::fabs(steer_deg) < p.lc_settle_steer_deg && d_lim && trk_lim;
  if (planted) {
    st.plant_n += 1;
  } else {
    st.plant_n = 0;
  }
  out.hold.plant_n = st.plant_n;
  if (planted && st.plant_n >= p.lc_done_hold_n) {
    out.hold.done = 1;
    out.hold.active = 0;
    st = LcPathSt{};
    return out;
  }

  out.hold.active = 1;
  if (st.reg != 0) {
    const float D = std::max(p.traj_horizon_floor_m, v * 2.0f);
    const float T = D / std::max(v, p.traj_speed_floor_mps);
    out.path = m_lat_traj(v, D, T, true, e_y, c1, c2, c3, 1.0e6f);
    return out;
  }
  const float remain = std::max(0.0f, st.L - st.s);
  out.path.horizon_m = remain;
  out.path.x_m[0] = 0.0f;
  out.path.y_m[0] = 0.0f;
  out.path.psi[0] = 0.0f;
  out.path.kappa[0] = k_s;
  out.path.delta[0] = d_s;
  const float c0 = std::cos(psi_use);
  const float s0 = std::sin(psi_use);
  const float ds = remain / static_cast<float>(std::max(n - 1, 1));
  for (int i = 1; i < n; ++i) {
    const float t = st.s + ds * static_cast<float>(i);
    const float xs = t;
    const float ys = clamp(st.W * lc_sigma(t / std::max(st.L, 1.0e-3f)), ylo, yhi);
    const float rx = xs - st.x;
    const float ry = ys - y_use;
    out.path.x_m[i] = rx * c0 + ry * s0;
    out.path.y_m[i] = -rx * s0 + ry * c0;
    float psi = 0.0f;
    float kap = 0.0f;
    float del = 0.0f;
    lc_geom(t, st.L, st.W, p.wheelbase_m, &psi, &kap, &del);
    out.path.psi[i] = psi - psi_use;
    out.path.kappa[i] = kap;
    out.path.delta[i] = del;
  }
  return out;
}

}  // namespace gf_octave_planning
