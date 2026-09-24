#pragma once

#include "gf_octave_planning/clamp.hpp"
#include "gf_octave_planning/plan_cal.hpp"

#include <algorithm>
#include <cmath>

// 1:1 octave_planning/afc/m_lat_follow.m — execute planned δ_ff.
// Rate limit only. Shares last with host-keep slew. Enter snaps last in m_ctrl.

namespace gf_octave_planning {

inline float& lat_cmd_last() {
  static float last = 0.0f;
  return last;
}

inline void m_lat_follow_reset() {
  lat_cmd_last() = 0.0f;
}

inline float m_lat_follow(float delta_ff, float /*steer_angle_deg*/ = 0.0f) {
  const PlanCal& p = plan_cal();
  float& last = lat_cmd_last();
  const float cmd = clamp(delta_ff, -p.lat_max_steer, p.lat_max_steer);
  const float ds = clamp(cmd - last, -p.lat_dsteer_max, p.lat_dsteer_max);
  last = last + ds;
  return last;
}

}  // namespace gf_octave_planning
