#pragma once

#include "gf_octave_planning/clamp.hpp"
#include "gf_octave_planning/plan_cal.hpp"

#include <cmath>

// 1:1 octave_planning/common/gf_lat_host_delta.m
// One host-keep law. Idle, after reg, after LC done. Ctrl does not synthesize.
// δ = −kψ c1 − atan(k e / v) − atan(L κ). c3 reserved (κ at x=0 uses c2).

namespace gf_octave_planning {

inline float gf_lat_host_delta(bool lane_valid, float e_y, float c1, float c2, float c3,
                               float v) {
  (void)c3;
  const PlanCal& p = plan_cal();
  if (!lane_usable(lane_valid, e_y, c1)) {
    return 0.0f;
  }
  const float e = clamp(e_y, -p.lat_e_sat_m, p.lat_e_sat_m);
  const float c1c = clamp(c1, -p.lat_c1_sat, p.lat_c1_sat);
  const float v_e = std::max(v, p.traj_speed_floor_mps);
  const float yp = c1c;
  const float ypp = 2.0f * c2;
  const float kappa = ypp / std::pow(1.0f + yp * yp, 1.5f);
  const float d = -p.lat_kpsi * c1c - std::atan(p.lc_reg_k * e / v_e) -
                  std::atan(p.wheelbase_m * kappa);
  return clamp(d, -p.lat_max_steer, p.lat_max_steer);
}

}  // namespace gf_octave_planning
