#pragma once

#include "gf_octave_planning/clamp.hpp"
#include "gf_octave_planning/lat_follow.hpp"
#include "gf_octave_planning/lat_host_delta.hpp"
#include "gf_octave_planning/plan_cal.hpp"

#include <cmath>

// 1:1 octave_planning/afc/m_lat_lka.m — slew host-keep. Desired is gf_lat_host_delta.

namespace gf_octave_planning {

inline float lat_steer_from_lane(float e_y, float c1, const PlanCal& p, float v = 0.0f,
                                 float c2 = 0.0f, float c3 = 0.0f) {
  (void)p;
  if (v <= 0.0f) {
    v = plan_cal().cruise_v_mps;
  }
  return gf_lat_host_delta(true, e_y, c1, c2, c3, v);
}

inline float lat_steer_from_ego(float /*steer_angle_deg*/) {
  return 0.0f;
}

inline float m_lat_lka(bool lane_valid, float e_y, float c1, float steer_angle_deg,
                       float v = 0.0f, float c2 = 0.0f, float c3 = 0.0f) {
  const PlanCal& p = plan_cal();
  if (v <= 0.0f) {
    v = p.cruise_v_mps;
  }
  const float d = gf_lat_host_delta(lane_valid, e_y, c1, c2, c3, v);
  return m_lat_follow(d, steer_angle_deg);
}

}  // namespace gf_octave_planning
