#pragma once

#include "gf_octave_planning/plan_cal.hpp"

#include <algorithm>
#include <cmath>

// LC layers (1:1 octave_planning/common/gf_lc_*.m). AFC keeps lc_side=0.
//   gf_lc_can     — neighbor time domain: T=L/v, front/rear/hard (not a metre stick)
//   gf_lc_host_ok — leave-host: opening skips ACC time-gap; host bumper still applies
//   gf_lc_weights — Host/Left/Right quality; leave && can. Host ignores rear.
//   gf_lc_side    — enter only; Hold/Settle freeze the side

namespace gf_octave_planning {

struct LcQuad {
  bool have_H{true};
  bool have_L{false};
  bool have_R{false};
  float d_H_f{120.0f};
  float d_H_hard{1.0e6f};
  float rel_H_f{0.0f};
  float hdg_H_f{0.0f};
  float d_H_r{35.0f};
  float rel_H_r{0.0f};
  float d_L_f{120.0f};
  float d_L_hard{1.0e6f};
  float rel_L_f{0.0f};
  float hdg_L_f{0.0f};
  float d_L_r{35.0f};
  float rel_L_r{0.0f};
  float d_R_f{120.0f};
  float d_R_hard{1.0e6f};
  float rel_R_f{0.0f};
  float hdg_R_f{0.0f};
  float d_R_r{35.0f};
  float rel_R_r{0.0f};
};

struct LcWeights {
  float H{0.0f};
  float L{0.0f};
  float R{0.0f};
  bool ok_H{false};
  bool ok_L{false};
  bool ok_R{false};
};

inline float gf_lc_L_need() {
  return plan_cal().d_lc_min_m;
}

inline float gf_lc_T_need(float v) {
  const PlanCal& p = plan_cal();
  return gf_lc_L_need() / std::max(v, p.traj_speed_floor_mps);
}

inline float gf_lc_t_need(float v) {
  return gf_lc_T_need(v);
}

inline bool gf_lc_same_way(float hdg) {
  return std::fabs(hdg) <= plan_cal().lc_hdg_same;
}

inline bool gf_lc_time_ok(float d, float close_mps, bool opening, float v, float T) {
  const PlanCal& p = plan_cal();
  if (d < p.d_lc_rear_min_m) {
    return false;
  }
  if (close_mps > p.closing_min_mps) {
    const float ttc = d / std::max(close_mps, 0.05f);
    if (ttc < T + p.lc_ttc_margin_s) {
      return false;
    }
  } else if (!opening) {
    if (d + 0.5f < std::max(p.acc_gap_min_m, std::max(0.0f, v) * p.acc_time_gap_s)) {
      return false;
    }
  }
  return true;
}

inline bool gf_lc_rear_ok(float d_r, float rel_r, float v) {
  const float T = gf_lc_T_need(v);
  if (T > plan_cal().t_lc_min_s) {
    return false;
  }
  return gf_lc_time_ok(d_r, std::max(0.0f, rel_r), rel_r < -0.3f, v, T);
}

inline bool gf_lc_host_ok(float d_f, float rel_f, float hdg_f, float v, float d_hard = 1.0e6f) {
  const PlanCal& p = plan_cal();
  if (d_f < p.d_lc_host_min_m) {
    return false;
  }
  const float T = gf_lc_T_need(v);
  if (d_f < 100.0f && !gf_lc_same_way(hdg_f)) {
    return false;
  }
  if (!gf_lc_time_ok(d_f, std::max(0.0f, -rel_f), true, v, T)) {
    return false;
  }
  if (!gf_lc_time_ok(d_hard, std::max(0.0f, v), false, v, T)) {
    return false;
  }
  return true;
}

inline bool gf_lc_hold_ok(float d_f, float d_r, float rel_r, float v, float d_hard = 1.0e6f,
                         float rel_f = 0.0f, float hdg_f = 0.0f) {
  const float T = gf_lc_T_need(v);
  if (d_f < 100.0f && !gf_lc_same_way(hdg_f)) {
    return false;
  }
  if (!gf_lc_time_ok(d_f, std::max(0.0f, -rel_f), rel_f > 0.3f, v, T)) {
    return false;
  }
  if (!gf_lc_time_ok(d_r, std::max(0.0f, rel_r), rel_r < -0.3f, v, T)) {
    return false;
  }
  if (!gf_lc_time_ok(d_hard, std::max(0.0f, v), false, v, T)) {
    return false;
  }
  return true;
}

inline bool gf_lc_can(bool have, float d_f, float d_r, float rel_r, float v, float D_see,
                     float d_hard = 1.0e6f, float rel_f = 0.0f, float hdg_f = 0.0f) {
  if (!have) {
    return false;
  }
  const float T = gf_lc_T_need(v);
  if (T > plan_cal().t_lc_min_s) {
    return false;
  }
  if (d_f < 100.0f && !gf_lc_same_way(hdg_f)) {
    return false;
  }
  if (!gf_lc_time_ok(d_f, std::max(0.0f, -rel_f), rel_f > 0.3f, v, T)) {
    return false;
  }
  if (!gf_lc_time_ok(d_r, std::max(0.0f, rel_r), rel_r < -0.3f, v, T)) {
    return false;
  }
  if (!gf_lc_time_ok(d_hard, std::max(0.0f, v), false, v, T)) {
    return false;
  }
  if (D_see < 0.0f) {
    return false;
  }
  return true;
}

inline float gf_lc_quality(float d_f, float d_r, float rel_r) {
  const PlanCal& p = plan_cal();
  d_f = std::min(std::max(0.0f, d_f), p.d_cal_cap_m);
  d_r = std::min(std::max(0.0f, d_r), p.d_lc_min_m);
  float s = d_f + 0.6f * d_r;
  if (rel_r > 0.3f) {
    const float ttc = d_r / std::max(rel_r, 0.05f);
    s -= std::max(0.0f, 8.0f - ttc) * 2.0f;
  }
  return s;
}

inline LcWeights gf_lc_weights(const LcQuad& q, float v, float D_see) {
  LcWeights w{};
  w.ok_H = q.have_H;
  if (w.ok_H) {
    w.H = gf_lc_quality(q.d_H_f, plan_cal().d_lc_min_m, 0.0f);
  }
  const bool leave = gf_lc_host_ok(q.d_H_f, q.rel_H_f, q.hdg_H_f, v, q.d_H_hard);
  w.ok_L = leave && gf_lc_can(q.have_L, q.d_L_f, q.d_L_r, q.rel_L_r, v, D_see, q.d_L_hard, q.rel_L_f,
                             q.hdg_L_f);
  if (w.ok_L) {
    w.L = gf_lc_quality(q.d_L_f, q.d_L_r, q.rel_L_r);
  }
  w.ok_R = leave && gf_lc_can(q.have_R, q.d_R_f, q.d_R_r, q.rel_R_r, v, D_see, q.d_R_hard, q.rel_R_f,
                             q.hdg_R_f);
  if (w.ok_R) {
    w.R = gf_lc_quality(q.d_R_f, q.d_R_r, q.rel_R_r);
  }
  return w;
}

inline float gf_lc_length(float v, float d_f, float D_see) {
  (void)v;
  (void)d_f;
  (void)D_see;
  return gf_lc_L_need();
}

inline int gf_lc_side(const LcQuad& q, float v, float D_see, int last = 0) {
  (void)last;
  const PlanCal& p = plan_cal();
  const LcWeights w = gf_lc_weights(q, v, D_see);
  const float host = w.H + p.lc_stay_m;
  if (w.ok_L && w.L > host) {
    if (w.ok_R && w.R > w.L + p.lc_left_bias_m && w.R > host) {
      return -1;
    }
    return 1;
  }
  if (w.ok_R && w.R > host) {
    return -1;
  }
  return 0;
}

}  // namespace gf_octave_planning
