#pragma once

#include "gf_octave_planning/clamp.hpp"

#include <algorithm>
#include <cmath>

// Demo cal — 1:1 with octave_planning/common/gf_plan_cal.m

namespace gf_octave_planning {

struct PlanCal {
  float lat_acc_m{3.2f};
  float lat_aeb_m{8.0f};
  float lat_merge_m{1.0f};
  float lon_max_d_m{80.0f};

  float t_base_s{10.0f};
  float t_plan_min_s{1.0f};
  float d_cal_cap_m{120.0f};
  float d_fov_conf_m{120.0f};
  float d_fov_conf_min{0.20f};
  float d_see_lane_bad_m{12.0f};
  float vis_up_alpha{0.08f};
  float d_vis_tight_m{40.0f};
  float a_req_vis_gain{1.25f};
  float traj_horizon_floor_m{8.0f};
  float traj_horizon_max_m{120.0f};

  int traj_n{16};
  int obj_n_max{8};

  float occ_w_min{0.40f};
  float cls_truck{2.0f};
  float t_lc_min_s{6.0f};
  float d_lc_min_m{40.0f};
  float lc_conf_min{0.50f};
  float cutin_head_gain{1.20f};

  float aeb_decel_mps2{6.0f};
  float aeb_d_min_m{4.5f};
  float aeb_margin_m{2.0f};
  float aeb_react_s{0.50f};
  float closing_min_mps{0.3f};
  float a_req_label_acc{0.12f};
  float a_req_label_aeb{0.85f};

  float cruise_v_mps{12.0f};
  float acc_time_gap_s{1.7f};
  float acc_gap_min_m{8.0f};
  float acc_gap_max_m{80.0f};
  float acc_gap_over_stop_m{6.0f};
  float acc_speed_db_mps{0.25f};
  float acc_thr_gain{0.11f};
  float acc_thr_max{0.50f};
  float acc_thr_hold{0.10f};
  float acc_brake_gain{0.22f};
  float acc_brake_min{0.08f};
  float acc_brake_max{0.85f};
  float acc_over_v_gain{0.28f};
  float cruise_standstill_v_mps{0.8f};
  float cruise_thr_standstill_min{0.42f};
  float cruise_thr_standstill_max{0.72f};
  float hold_brake{0.22f};

  float lat_ky{0.38f};
  float lat_kpsi{0.65f};
  float lat_max_steer{0.42f};
  float lat_e_sat_m{1.8f};
  float lat_e_desense_hi_m{1.2f};
  float lat_e_desense_lo_m{0.6f};
  float lat_ky_scale_hi{0.30f};
  float lat_ky_scale_lo{0.50f};
  float lat_c1_sat{0.40f};
  float lat_dsteer_max{0.055f};
  float lat_ey_invalid_m{3.0f};
  float lat_c1_invalid{0.40f};
  float lat_ey_slow_m{1.0f};

  float traj_blend_m{14.0f};
  float traj_speed_floor_mps{0.2f};
};

struct PlanHorizon {
  float D_see{120.0f};
  float T_plan{10.0f};
};

inline const PlanCal& plan_cal() {
  static const PlanCal kDemo{};
  return kDemo;
}

inline bool lane_usable(bool lane_valid, float e_y, float c1) {
  const PlanCal& p = plan_cal();
  return lane_valid && std::fabs(e_y) <= p.lat_ey_invalid_m &&
         std::fabs(c1) <= p.lat_c1_invalid;
}

inline float lon_d_stop(float v) {
  const PlanCal& p = plan_cal();
  const float a = std::max(p.aeb_decel_mps2, 0.5f);
  const float vv = std::max(0.0f, v);
  return (vv * vv) / (2.0f * a) + vv * p.aeb_react_s + p.aeb_d_min_m + p.aeb_margin_m;
}

inline float lon_desired_gap(float v) {
  const PlanCal& p = plan_cal();
  float g = std::max(p.acc_gap_min_m, std::max(0.0f, v) * p.acc_time_gap_s);
  const float floor = lon_d_stop(v) + p.acc_gap_over_stop_m;
  g = std::max(g, floor);
  g = std::min(g, p.acc_gap_max_m);
  return std::max(g, floor);
}

inline float plan_lat_weight(float alat) {
  const PlanCal& p = plan_cal();
  const float aa = std::fabs(alat);
  if (aa >= p.lat_aeb_m) {
    return 0.0f;
  }
  if (aa <= p.lat_merge_m) {
    return 1.0f;
  }
  return clamp(1.0f - (aa - p.lat_merge_m) / std::max(p.lat_aeb_m - p.lat_merge_m, 0.1f), 0.0f,
               1.0f);
}

inline float plan_v_cap_vis(float D_see) {
  const PlanCal& p = plan_cal();
  const float a = std::max(p.aeb_decel_mps2, 0.5f);
  const float vc = std::sqrt(std::max(0.0f, 2.0f * a * std::max(0.0f, D_see - p.aeb_d_min_m)));
  return std::min(vc, p.cruise_v_mps);
}

// Fall immediately, rise by alpha. 1:1 gf_plan_vis_slew.m
inline float plan_vis_slew(float raw, float prev, float alpha) {
  if (prev <= 0.0f) {
    return raw;
  }
  if (raw < prev) {
    return raw;
  }
  return prev + alpha * (raw - prev);
}

inline PlanHorizon plan_horizon(float v, bool lane_valid, float e_y, float c1, float x_end,
                               float D_occ, float D_fov, float D_see_prev, float T_plan_prev) {
  const PlanCal& p = plan_cal();
  PlanHorizon h{};
  float D_vr = p.d_cal_cap_m;
  if (lane_usable(lane_valid, e_y, c1)) {
    if (x_end > 0.5f) {
      D_vr = x_end;
    }
  } else {
    D_vr = std::min(D_vr, p.d_see_lane_bad_m);
  }
  const float D_raw = std::min({D_fov, D_vr, D_occ, p.d_cal_cap_m});
  h.D_see = plan_vis_slew(D_raw, D_see_prev, p.vis_up_alpha);
  float T_raw = std::min(p.t_base_s, h.D_see / std::max(v, p.traj_speed_floor_mps));
  T_raw = std::max(T_raw, p.t_plan_min_s);
  h.T_plan = plan_vis_slew(T_raw, T_plan_prev, p.vis_up_alpha);
  return h;
}

inline PlanHorizon plan_horizon(float v, bool lane_valid, float e_y, float c1, float x_end) {
  const PlanCal& p = plan_cal();
  return plan_horizon(v, lane_valid, e_y, c1, x_end, p.d_cal_cap_m, p.d_fov_conf_m, 0.0f, 0.0f);
}

// 1:1 gf_lon_a_req.m — 6-arg w is take-strict (already weighted).
inline float lon_a_req(float v, bool lead_valid, float d, float rel, float lat, float w) {
  const PlanCal& p = plan_cal();
  if (!lead_valid || w <= 0.0f || d > p.lon_max_d_m) {
    return 0.0f;
  }
  const float d_use = std::max(d, 0.05f);
  const float a = std::max(p.aeb_decel_mps2, 0.5f);
  const float gap = std::max(d_use - p.aeb_d_min_m, 0.2f);
  const float vv = std::max(0.0f, v);
  const float v_obj = std::max(0.0f, vv + rel);
  float a_req = 0.0f;
  if (v_obj < 0.3f) {
    const float v_safe = std::sqrt(std::max(0.0f, 2.0f * a * gap));
    if (vv > v_safe) {
      a_req = std::min(a, (vv * vv) / (2.0f * gap));
    }
  } else {
    const float v_safe = std::sqrt(v_obj * v_obj + 2.0f * a * gap);
    if (vv > v_safe) {
      a_req = std::min(a, (vv * vv - v_obj * v_obj) / (2.0f * gap));
    }
  }
  if (d_use < p.aeb_d_min_m) {
    a_req = a;
  }
  return a_req * w;
}

inline float lon_a_req(float v, bool lead_valid, float d, float rel, float lat) {
  return lon_a_req(v, lead_valid, d, rel, lat, plan_lat_weight(lat));
}

}  // namespace gf_octave_planning
