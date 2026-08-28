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

// 1:1 gf_plan_obj_weight.m
inline float plan_obj_weight(float lat, float heading, float is_ped) {
  const PlanCal& p = plan_cal();
  float w = plan_lat_weight(lat);
  if (is_ped != 0.0f && std::fabs(lat) < p.lat_aeb_m) {
    w = std::max(w, 0.85f);
  }
  if (lat * heading < -0.02f) {
    w = std::min(1.0f, w + p.cutin_head_gain * std::min(std::fabs(heading), 0.5f));
  }
  return w;
}

// 1:1 gf_plan_occlusion.m — walks compact rows only.
inline float plan_occlusion(const PlanObj* obj, int n) {
  const PlanCal& p = plan_cal();
  float D_occ = p.d_cal_cap_m;
  n = clamp_nobj(n);
  if (n < 1 || obj == nullptr) {
    return D_occ;
  }
  for (int k = 0; k < n; ++k) {
    const float w = plan_lat_weight(obj[k].lat);
    if (w < p.occ_w_min) {
      continue;
    }
    const float near = std::max(0.0f, obj[k].d - 0.5f * obj[k].len_m);
    if (obj[k].cls == p.cls_truck || w > 0.85f) {
      D_occ = std::min(D_occ, near);
    }
  }
  return D_occ;
}

// 1:1 gf_plan_v_at_s.m (obj already unpacked).
inline float plan_v_at_s(float s, float v_ego, const PlanObj* obj, int n, float D_see,
                         bool lane_ok) {
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
    const float w = plan_obj_weight(obj[k].lat, obj[k].heading, obj[k].is_ped);
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
inline float plan_v_at_s(float s, float v_ego, bool lead_valid, float d, float rel, float lat,
                         float D_see, bool lane_ok) {
  if (!lead_valid) {
    return plan_v_at_s(s, v_ego, static_cast<const PlanObj*>(nullptr), 0, D_see, lane_ok);
  }
  PlanObj one{};
  one.d = d;
  one.rel = rel;
  one.lat = lat;
  one.len_m = 4.5f;
  one.cls = 1.0f;
  return plan_v_at_s(s, v_ego, &one, 1, D_see, lane_ok);
}

inline void plan_speed_profile(const float* x_m, int npts, float v_ego, const PlanObj* obj, int nobj,
                               float D_see, bool lane_ok, float* v_s) {
  if (x_m == nullptr || v_s == nullptr || npts < 1) {
    return;
  }
  for (int i = 0; i < npts; ++i) {
    v_s[i] = plan_v_at_s(x_m[i], v_ego, obj, nobj, D_see, lane_ok);
  }
}

// 1:1 gf_lon_a_req_n.m
inline float lon_a_req_n(float v, const PlanObj* obj, int n) {
  float a_req = 0.0f;
  n = clamp_nobj(n);
  if (n < 1 || obj == nullptr) {
    return a_req;
  }
  for (int k = 0; k < n; ++k) {
    const float w = plan_obj_weight(obj[k].lat, obj[k].heading, obj[k].is_ped);
    const float ak = lon_a_req(v, true, obj[k].d, obj[k].rel, obj[k].lat, w);
    if (ak > a_req) {
      a_req = ak;
    }
  }
  return a_req;
}

}  // namespace gf_octave_planning
