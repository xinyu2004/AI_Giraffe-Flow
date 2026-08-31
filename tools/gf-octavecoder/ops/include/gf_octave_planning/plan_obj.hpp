#pragma once

#include "gf_octave_planning/plan_cal.hpp"

#include <algorithm>
#include <cmath>

// Compact n×7 rows. Unpack perc once in the shell; ops never re-walk FCM blobs.
// 1:1 octave_planning/common/gf_plan_obj_*.m + gf_lon_a_req_n.m / gf_plan_v_at_s.m

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

// 1:1 gf_plan_obj_weight.m
inline float plan_obj_weight(float lat, float heading, float is_ped, float len_m, float cls,
                             float c0) {
  const PlanCal& p = plan_cal();
  const float occupy = plan_lane_occupy(c0, lat, len_m, cls, heading, is_ped);
  float w = plan_can_pass(occupy, cls, is_ped) ? 0.0f : 1.0f;
  const float wo = plan_obj_width(cls, is_ped);
  const float half =
      0.5f * (wo * std::fabs(std::cos(heading)) + std::max(len_m, 0.5f) * std::fabs(std::sin(heading)));
  const float gap = (std::fabs(lat - c0) - half) - 0.5f * p.lane_width_m;
  if (gap < p.cutin_approach_m && lat * heading < -0.02f) {
    w = std::min(1.0f, std::max(w, 0.55f) + p.cutin_head_gain * std::min(std::fabs(heading), 0.5f));
  }
  return w;
}

inline float plan_obj_weight(float lat, float heading, float is_ped) {
  return plan_obj_weight(lat, heading, is_ped, 4.5f, 1.0f, 0.0f);
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

// 1:1 gf_plan_v_at_s.m (obj already unpacked).
inline float plan_v_at_s(float s, float v_ego, const PlanObj* obj, int n, float D_see,
                         bool lane_ok, float c0) {
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
                                   obj[k].cls, c0);
    if (w <= 0.0f) {
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
    const float v_gap = std::max(0.0f, (gap - p.acc_gap_min_m) / std::max(p.acc_time_gap_s, 0.2f));
    const float v_lim = std::min(v_kin, v_gap);
    vi = std::min(vi, v_lim * w + v_cap * (1.0f - w));
  }
  return vi;
}

// Single-lead wrapper — 1:1 m_lon_acc_aeb.m packing one row.
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
                               float D_see, bool lane_ok, float* v_s, float c0) {
  if (x_m == nullptr || v_s == nullptr || npts < 1) {
    return;
  }
  for (int i = 0; i < npts; ++i) {
    v_s[i] = plan_v_at_s(x_m[i], v_ego, obj, nobj, D_see, lane_ok, c0);
  }
}

inline void plan_speed_profile(const float* x_m, int npts, float v_ego, const PlanObj* obj, int nobj,
                               float D_see, bool lane_ok, float* v_s) {
  plan_speed_profile(x_m, npts, v_ego, obj, nobj, D_see, lane_ok, v_s, 0.0f);
}

// 1:1 gf_lon_a_req_n.m
inline float lon_a_req_n(float v, const PlanObj* obj, int n, float c0) {
  float a_req = 0.0f;
  n = clamp_nobj(n);
  if (n < 1 || obj == nullptr) {
    return a_req;
  }
  for (int k = 0; k < n; ++k) {
    const float w = plan_obj_weight(obj[k].lat, obj[k].heading, obj[k].is_ped, obj[k].len_m,
                                   obj[k].cls, c0);
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
