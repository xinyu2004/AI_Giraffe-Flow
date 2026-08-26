#pragma once

#include "gf_octave_planning/clamp.hpp"
#include "gf_octave_planning/plan_cal.hpp"

#include <cmath>

// Corresponds to octave_planning/afc/m_lat_lka.m — thresholds from plan_cal().
// lat_dsteer_max rate limit lives inside LKA (same as .m persistent).
namespace gf_octave_planning {

inline float lat_steer_from_lane(float e_y, float c1, const PlanCal& p) {
  float ky = p.lat_ky;
  const float e = clamp(e_y, -p.lat_e_sat_m, p.lat_e_sat_m);
  const float ae = std::fabs(e);
  if (ae > p.lat_e_desense_hi_m) {
    ky *= p.lat_ky_scale_hi;
  } else if (ae > p.lat_e_desense_lo_m) {
    ky *= p.lat_ky_scale_lo;
  }
  const float c1c = clamp(c1, -p.lat_c1_sat, p.lat_c1_sat);
  const float cmd = -ky * e - p.lat_kpsi * c1c;
  return clamp(cmd, -p.lat_max_steer, p.lat_max_steer);
}

inline float lat_steer_from_ego(float /*steer_angle_deg*/) {
  return 0.0f;
}

inline float m_lat_lka(bool lane_valid, float e_y, float c1, float steer_angle_deg) {
  static float last_steer = 0.0f;
  const PlanCal& p = plan_cal();
  float cmd = 0.0f;
  if (lane_usable(lane_valid, e_y, c1)) {
    cmd = lat_steer_from_lane(e_y, c1, p);
  } else {
    cmd = lat_steer_from_ego(steer_angle_deg);
  }
  const float ds = clamp(cmd - last_steer, -p.lat_dsteer_max, p.lat_dsteer_max);
  last_steer = last_steer + ds;
  return last_steer;
}

}  // namespace gf_octave_planning
