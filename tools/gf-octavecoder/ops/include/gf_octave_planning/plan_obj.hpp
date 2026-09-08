#pragma once

#include "gf_octave_planning/plan_cal.hpp"

#include <algorithm>
#include <cmath>

// Compact n×7 rows. Unpack perc once in the shell; ops never re-walk FCM blobs.
// Lon composition (1:1 m_plan_tick.m):
//   D_see = slew(min(D_vr, D_occ, D_fov, cap))     — marks / occupy / optics
//   s_stop = plan_reg_stop(TSR)                    — known light, not gated on D_see
//   v(s) = min(vis, v_reg(s_stop), peers, follow)  — light is a speed profile
//   a_req = lon_a_req_n(occupy) + lon_a_req_stop(late/at-line)

namespace gf_octave_planning {

inline constexpr int kObjNMax = 8;

struct PlanObj {
  float d{0.0f};
  float rel{0.0f};
  float lat{0.0f};
  float len_m{4.5f};
  float cls{1.0f};
  float heading{0.0f};
  float is_ped{0.0f};
};

inline int clamp_nobj(int n) {
  const int cap = std::max(0, plan_cal().obj_n_max);
  if (n < 1) {
    return 0;
  }
  return std::min({n, cap, kObjNMax});
}

// 1:1 gf_plan_is_reg_stop.m
inline bool plan_is_reg_stop(float cls) {
  return cls == plan_cal().cls_reg_stop;
}

// 1:1 gf_plan_reg_stop.m — TSR stop-line station. None / light gone → d_cal_cap.
// Packed light with s_line<=0 → hold (do not release). Not hidden by D_see.
inline float plan_reg_stop(const PlanObj* obj, int n, float c0) {
  const PlanCal& p = plan_cal();
  float s_stop = p.d_cal_cap_m;
  n = clamp_nobj(n);
  if (n < 1 || obj == nullptr) {
    return s_stop;
  }
  const float hold = std::max(p.reg_stop_hold_m, 0.2f);
  const float behind = std::max(p.reg_stop_behind_m, 0.0f);
  for (int k = 0; k < n; ++k) {
    if (!plan_is_reg_stop(obj[k].cls)) {
      continue;
    }
    if (std::fabs(obj[k].lat - c0) > p.reg_stop_lat_m) {
      continue;
    }
    if (obj[k].d < -behind || obj[k].d > p.lon_max_d_m) {
      continue;
    }
    const float s_line = obj[k].d - p.reg_stop_margin_m;
    if (s_line <= 0.0f) {
      if (hold < s_stop) {
        s_stop = hold;
      }
    } else if (s_line < s_stop) {
      s_stop = s_line;
    }
  }
  return s_stop;
}

inline float plan_reg_stop(const PlanObj* obj, int n) {
  return plan_reg_stop(obj, n, 0.0f);
}

// 1:1 gf_plan_v_reg.m — comfort / late speed to stop at the line. Not AEB.
// Within hold → 0. Kinematics only — not acc_time_gap (follow).
inline float plan_v_reg(float s, float s_stop, float v_ego = 0.0f) {
  const PlanCal& p = plan_cal();
  if (s_stop <= 0.0f || s_stop >= (p.d_cal_cap_m - 0.5f)) {
    return 1.0e6f;
  }
  const float hold = std::max(p.reg_stop_hold_m, 0.2f);
  const float gap = s_stop - s;
  if (gap <= hold) {
    return 0.0f;
  }
  float a = std::max(p.reg_stop_decel_mps2, 0.5f);
  const float vv = std::max(0.0f, v_ego);
  const float s_need = (vv * vv) / (2.0f * a) + hold;
  if (gap < s_need) {
    a = std::max(p.reg_stop_late_mps2, a);
  }
  return std::sqrt(std::max(0.0f, 2.0f * a * (gap - hold)));
}

// 1:1 gf_lon_a_req_stop.m — late / at-line / hold-band brake. Comfort-enough → 0.
inline float lon_a_req_stop(float v, float s_stop) {
  const PlanCal& p = plan_cal();
  if (s_stop <= 0.0f || s_stop >= (p.d_cal_cap_m - 0.5f)) {
    return 0.0f;
  }
  const float hold = std::max(p.reg_stop_hold_m, 0.2f);
  const float a_c = std::max(p.reg_stop_decel_mps2, 0.5f);
  const float a_late = std::max(p.reg_stop_late_mps2, a_c);
  const float vv = std::max(0.0f, v);
  if (s_stop <= hold) {
    return (vv > 0.05f) ? a_late : 0.0f;
  }
  const float s_need = (vv * vv) / (2.0f * a_c) + hold;
  if (s_stop > s_need + 0.05f) {
    return 0.0f;
  }
  const float a_kin = (vv * vv) / (2.0f * std::max(s_stop - hold, 0.2f));
  return std::min(a_late, std::max(0.0f, a_kin));
}

// 1:1 gf_plan_obj_width.m
inline float plan_obj_width(float cls, float is_ped) {
  const PlanCal& p = plan_cal();
  if (is_ped != 0.0f || cls == p.cls_ped) {
    return p.obj_width_ped_m;
  }
  if (cls == p.cls_truck) {
    return p.obj_width_truck_m;
  }
  return p.obj_width_car_m;
}

// 1:1 gf_plan_lane_occupy.m
inline float plan_lane_occupy(float c0, float lat, float len_m, float cls, float heading,
                             float is_ped) {
  if (plan_is_reg_stop(cls)) {
    return 0.0f;
  }
  const PlanCal& p = plan_cal();
  const float W = p.lane_width_m;
  const float wo = plan_obj_width(cls, is_ped);
  const float half = 0.5f * (wo * std::fabs(std::cos(heading)) + std::max(len_m, 0.5f) * std::fabs(std::sin(heading)));
  const float y0 = c0 - 0.5f * W;
  const float y1 = c0 + 0.5f * W;
  const float o0 = lat - half;
  const float o1 = lat + half;
  return std::max(0.0f, std::min(y1, o1) - std::max(y0, o0));
}

// 1:1 gf_plan_can_pass.m
inline bool plan_can_pass(float occupy, float cls, float is_ped) {
  const PlanCal& p = plan_cal();
  if ((is_ped != 0.0f || cls == p.cls_ped) && occupy > 1.0e-3f) {
    return false;
  }
  return (p.lane_width_m - occupy) >= (p.ego_width_m + p.pass_clear_m);
}

// 1:1 gf_plan_obj_weight.m — cut-in needs closing rel.
inline float plan_obj_weight(float lat, float heading, float is_ped, float len_m, float cls,
                             float c0, float rel = 0.0f) {
  if (plan_is_reg_stop(cls)) {
    return 0.0f;
  }
  const PlanCal& p = plan_cal();
  const float occupy = plan_lane_occupy(c0, lat, len_m, cls, heading, is_ped);
  float w = plan_can_pass(occupy, cls, is_ped) ? 0.0f : 1.0f;
  const float wo = plan_obj_width(cls, is_ped);
  const float half =
      0.5f * (wo * std::fabs(std::cos(heading)) + std::max(len_m, 0.5f) * std::fabs(std::sin(heading)));
  const float gap = (std::fabs(lat - c0) - half) - 0.5f * p.lane_width_m;
  const bool closing = rel < -p.cutin_close_mps;
  if (gap < p.cutin_approach_m && lat * heading < -0.02f && closing) {
    w = std::min(1.0f, std::max(w, 0.55f) + p.cutin_head_gain * std::min(std::fabs(heading), 0.5f));
  }
  return w;
}

inline float plan_obj_weight(float lat, float heading, float is_ped) {
  return plan_obj_weight(lat, heading, is_ped, 4.5f, 1.0f, 0.0f, 0.0f);
}

// 1:1 gf_plan_v_peers.m — match moving adjacent flow. Not occupy, not parked.
inline float plan_v_peers(float s, float v_ego, const PlanObj* obj, int n, float c0) {
  const PlanCal& p = plan_cal();
  float vi = 1.0e6f;
  n = clamp_nobj(n);
  if (n < 1 || obj == nullptr) {
    return vi;
  }
  const float vv = std::max(0.0f, v_ego);
  const float half_w = 0.5f * p.lane_width_m;
  for (int k = 0; k < n; ++k) {
    if (plan_is_reg_stop(obj[k].cls)) {
      continue;
    }
    if (obj[k].d <= s || obj[k].d > p.peer_d_max_m) {
      continue;
    }
    const float alat = std::fabs(obj[k].lat - c0);
    if (alat <= half_w || alat > p.peer_lat_max_m) {
      continue;
    }
    const float w = plan_obj_weight(obj[k].lat, obj[k].heading, obj[k].is_ped, obj[k].len_m,
                                   obj[k].cls, c0, obj[k].rel);
    if (w > 0.5f) {
      continue;
    }
    const float v_obj = std::max(0.0f, vv + obj[k].rel);
    if (v_obj < p.peer_v_min_mps) {
      continue;
    }
    vi = std::min(vi, v_obj);
  }
  return vi;
}

// 1:1 gf_plan_occlusion.m
inline float plan_occlusion(const PlanObj* obj, int n, float c0) {
  const PlanCal& p = plan_cal();
  float D_occ = p.d_cal_cap_m;
  n = clamp_nobj(n);
  if (n < 1 || obj == nullptr) {
    return D_occ;
  }
  for (int k = 0; k < n; ++k) {
    if (plan_is_reg_stop(obj[k].cls)) {
      continue;
    }
    const float occupy =
        plan_lane_occupy(c0, obj[k].lat, obj[k].len_m, obj[k].cls, obj[k].heading, obj[k].is_ped);
    if (occupy < p.occ_overlap_min_m) {
      continue;
    }
    const float near = std::max(0.0f, obj[k].d - 0.5f * obj[k].len_m);
    D_occ = std::min(D_occ, near);
  }
  return D_occ;
}

inline float plan_occlusion(const PlanObj* obj, int n) {
  return plan_occlusion(obj, n, 0.0f);
}

// 1:1 gf_plan_v_at_s.m (obj already unpacked). s_stop once per tick.
// v_sign_* = DSTSR speed limits (mps); not plan_v_cap_vis (sight).
inline float plan_v_at_s(float s, float v_ego, const PlanObj* obj, int n, float D_see,
                         bool lane_ok, float c0, float s_stop, float v_sign_max,
                         float v_sign_min) {
  const PlanCal& p = plan_cal();
  const float v_cap = plan_v_cap_vis(D_see);
  if (!lane_ok) {
    return 0.0f;
  }
  if (s > D_see + 0.05f) {
    return 0.0f;
  }
  float vi = v_cap;
  n = clamp_nobj(n);
  vi = std::min(vi, v_sign_max);
  if (v_sign_min > 0.5f && s_stop >= (p.d_cal_cap_m - 0.5f)) {
    vi = std::max(vi, std::min(v_sign_min, std::min(v_sign_max, v_cap)));
  }
  vi = std::min(vi, plan_v_reg(s, s_stop, v_ego));
  vi = std::min(vi, plan_v_peers(s, v_ego, obj, n, c0));
  if (n < 1 || obj == nullptr) {
    return vi;
  }
  const float a = std::max(p.aeb_decel_mps2, 0.5f);
  const float vv = std::max(0.0f, v_ego);
  for (int k = 0; k < n; ++k) {
    if (obj[k].d > p.lon_max_d_m) {
      continue;
    }
    const float w = plan_obj_weight(obj[k].lat, obj[k].heading, obj[k].is_ped, obj[k].len_m,
                                   obj[k].cls, c0, obj[k].rel);
    if (w <= 0.0f) {
      continue;
    }
    if (obj[k].rel > p.cutin_close_mps && w < 1.0f) {
      continue;
    }
    const float gap = obj[k].d - s;
    if (gap <= p.aeb_d_min_m) {
      if (w > 0.5f) {
        vi = 0.0f;
      }
      continue;
    }
    const float v_obj = std::max(0.0f, vv + obj[k].rel);
    const float v_kin = std::sqrt(std::max(0.0f, v_obj * v_obj + 2.0f * a * (gap - p.aeb_d_min_m)));
    // Gap-error follow (1:1 gf_plan_v_at_s.m): close when open, open when tight.
    const float desired =
        p.acc_gap_min_m + p.acc_time_gap_s * std::max(v_obj, 0.5f);
    const float v_follow =
        v_obj + std::max(-4.0f, std::min(3.0f, 0.4f * (gap - desired)));
    float v_lim = v_kin;
    if (w >= 1.0f || obj[k].rel <= 0.0f) {
      v_lim = std::min(v_kin, std::max(0.0f, v_follow));
    }
    vi = std::min(vi, v_lim * w + v_cap * (1.0f - w));
  }
  return vi;
}

inline float plan_v_at_s(float s, float v_ego, const PlanObj* obj, int n, float D_see,
                         bool lane_ok, float c0, float s_stop) {
  return plan_v_at_s(s, v_ego, obj, n, D_see, lane_ok, c0, s_stop, 1.0e6f, 0.0f);
}

// Single-lead wrapper — 1:1 m_lon_acc_aeb.m packing one row.
inline float plan_v_at_s(float s, float v_ego, const PlanObj* obj, int n, float D_see,
                         bool lane_ok, float c0) {
  return plan_v_at_s(s, v_ego, obj, n, D_see, lane_ok, c0, plan_reg_stop(obj, n, c0));
}

inline float plan_v_at_s(float s, float v_ego, const PlanObj* obj, int n, float D_see,
                         bool lane_ok) {
  return plan_v_at_s(s, v_ego, obj, n, D_see, lane_ok, 0.0f);
}

inline float plan_v_at_s(float s, float v_ego, bool lead_valid, float d, float rel, float lat,
                         float D_see, bool lane_ok) {
  if (!lead_valid) {
    return plan_v_at_s(s, v_ego, static_cast<const PlanObj*>(nullptr), 0, D_see, lane_ok, 0.0f);
  }
  PlanObj one{};
  one.d = d;
  one.rel = rel;
  one.lat = lat;
  one.len_m = 4.5f;
  one.cls = 1.0f;
  return plan_v_at_s(s, v_ego, &one, 1, D_see, lane_ok, 0.0f);
}

inline void plan_speed_profile(const float* x_m, int npts, float v_ego, const PlanObj* obj, int nobj,
                               float D_see, bool lane_ok, float* v_s, float c0, float s_stop,
                               float v_sign_max, float v_sign_min) {
  if (x_m == nullptr || v_s == nullptr || npts < 1) {
    return;
  }
  for (int i = 0; i < npts; ++i) {
    v_s[i] = plan_v_at_s(x_m[i], v_ego, obj, nobj, D_see, lane_ok, c0, s_stop, v_sign_max,
                         v_sign_min);
  }
}

inline void plan_speed_profile(const float* x_m, int npts, float v_ego, const PlanObj* obj, int nobj,
                               float D_see, bool lane_ok, float* v_s, float c0, float s_stop) {
  plan_speed_profile(x_m, npts, v_ego, obj, nobj, D_see, lane_ok, v_s, c0, s_stop, 1.0e6f, 0.0f);
}

inline void plan_speed_profile(const float* x_m, int npts, float v_ego, const PlanObj* obj, int nobj,
                               float D_see, bool lane_ok, float* v_s, float c0) {
  plan_speed_profile(x_m, npts, v_ego, obj, nobj, D_see, lane_ok, v_s, c0,
                     plan_reg_stop(obj, nobj, c0));
}

inline void plan_speed_profile(const float* x_m, int npts, float v_ego, const PlanObj* obj, int nobj,
                               float D_see, bool lane_ok, float* v_s) {
  plan_speed_profile(x_m, npts, v_ego, obj, nobj, D_see, lane_ok, v_s, 0.0f);
}

// 1:1 gf_lon_a_req_n.m — host-lane occupy only. Lights are v_reg, not here.
inline float lon_a_req_n(float v, const PlanObj* obj, int n, float c0) {
  float a_req = 0.0f;
  n = clamp_nobj(n);
  if (n < 1 || obj == nullptr) {
    return a_req;
  }
  for (int k = 0; k < n; ++k) {
    if (plan_is_reg_stop(obj[k].cls)) {
      continue;
    }
    const float w = plan_obj_weight(obj[k].lat, obj[k].heading, obj[k].is_ped, obj[k].len_m,
                                   obj[k].cls, c0, obj[k].rel);
    const float ak = lon_a_req(v, true, obj[k].d, obj[k].rel, obj[k].lat, w);
    if (ak > a_req) {
      a_req = ak;
    }
  }
  return a_req;
}

inline float lon_a_req_n(float v, const PlanObj* obj, int n) {
  return lon_a_req_n(v, obj, n, 0.0f);
}

}  // namespace gf_octave_planning
