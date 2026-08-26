#pragma once

#include "gf_octave_planning/clamp.hpp"
#include "gf_octave_planning/plan_cal.hpp"

#include <algorithm>
#include <cmath>

// Corresponds to octave_planning/afc/m_lon_acc_aeb.m + gf_lon_exec.m

namespace gf_octave_planning {

struct LonCtrl {
  float throttle{0.35f};
  float brake{0.0f};
  float target_speed_mps{12.0f};
  const char* mode{"cruise"};
};

inline LonCtrl lon_exec(float v, float v_plan, float a_req) {
  const PlanCal& p = plan_cal();
  v = std::max(0.0f, v);
  v_plan = std::max(0.0f, v_plan);
  const float a_max = std::max(p.aeb_decel_mps2, 0.5f);
  const float brk_req = clamp(a_req / a_max, 0.0f, 1.0f);
  LonCtrl c{};
  c.target_speed_mps = v_plan;
  c.mode = "cruise";
  const float err = v_plan - v;

  if (brk_req >= p.a_req_label_aeb) {
    c.throttle = 0.0f;
    c.brake = 1.0f;
    c.mode = "aeb";
    return c;
  }
  if (brk_req >= p.a_req_label_acc) {
    c.throttle = 0.0f;
    c.brake = clamp(brk_req, p.acc_brake_min, 1.0f);
    c.mode = "acc";
    return c;
  }
  if (v_plan < 0.4f) {
    c.throttle = 0.0f;
    c.brake = (v > 0.4f) ? p.hold_brake : 0.0f;
    return c;
  }
  if (v > v_plan + p.acc_speed_db_mps) {
    c.throttle = 0.0f;
    c.brake = clamp((v - v_plan) * p.acc_over_v_gain, p.acc_brake_min, p.acc_brake_max);
    c.mode = "acc";
    return c;
  }
  if (err >= p.acc_speed_db_mps) {
    if (v < p.cruise_standstill_v_mps) {
      c.throttle = clamp(0.48f + err * 0.04f, p.cruise_thr_standstill_min,
                         p.cruise_thr_standstill_max);
    } else {
      c.throttle = clamp(0.14f + err * p.acc_thr_gain, 0.0f, p.acc_thr_max);
    }
    c.brake = 0.0f;
    return c;
  }
  c.throttle = p.acc_thr_hold;
  c.brake = 0.0f;
  return c;
}

inline LonCtrl m_lon_acc_aeb(float v, bool lead_valid, float d, float rel,
                             float lead_lat_m = 0.0f, float e_y = 0.0f, float c1 = 0.0f,
                             bool lane_valid = true) {
  const PlanCal& p = plan_cal();
  v = std::max(0.0f, v);
  const PlanHorizon h = plan_horizon(v, lane_valid, e_y, c1, 1.0e6f);
  bool lane_ok = lane_usable(lane_valid, e_y, c1);
  if (std::fabs(e_y) > p.lat_ey_slow_m) {
    lane_ok = false;
  }
  const float v_plan =
      plan_v_at_s(0.0f, v, lead_valid, d, rel, lead_lat_m, h.D_see, lane_ok);
  float a_req = lon_a_req(v, lead_valid, d, rel, lead_lat_m);
  if (!lane_ok) {
    a_req = std::max(a_req, 0.0f);
    return lon_exec(v, 0.0f, a_req);
  }
  return lon_exec(v, v_plan, a_req);
}

}  // namespace gf_octave_planning
