#pragma once

#include "gf_octave_planning/clamp.hpp"
#include "gf_octave_planning/plan_cal.hpp"

#include <algorithm>
#include <cmath>

// Corresponds to octave_planning/afc/m_lat_traj.m
namespace gf_octave_planning {

inline constexpr int kLatTrajPoints = 16;

struct LatTraj {
  float x_m[kLatTrajPoints]{};
  float y_m[kLatTrajPoints]{};
  float v_mps[kLatTrajPoints]{};
  float horizon_m{25.0f};
  float T_plan_s{10.0f};
};

inline float lat_poly_y(float x, float c0, float c1, float c2, float c3) {
  return c0 + c1 * x + c2 * x * x + c3 * x * x * x;
}

inline float lat_blend_alpha(float x, float blend_len_m) {
  return 1.0f - std::exp(-x / blend_len_m);
}

inline LatTraj m_lat_traj(float speed_mps, float D_see, float T_plan, bool lane_valid, float c0,
                          float c1, float c2, float c3, float x_end) {
  const PlanCal& p = plan_cal();
  LatTraj t{};
  t.T_plan_s = T_plan;
  const bool use_lane = lane_usable(lane_valid, c0, c1);
  const float v = std::max(speed_mps, p.traj_speed_floor_mps);
  float D_plan = std::min({D_see, v * T_plan, p.traj_horizon_max_m});
  if (use_lane && x_end > 0.5f) {
    D_plan = std::min(D_plan, x_end);
  }
  D_plan = std::min(D_plan, D_see);
  D_plan = std::max(D_plan, p.traj_horizon_floor_m);
  if (D_plan > D_see) {
    D_plan = std::max(D_see, 1.0f);
  }
  t.horizon_m = D_plan;
  const int n = std::min(kLatTrajPoints, std::max(2, p.traj_n));
  const float ds = t.horizon_m / static_cast<float>(n - 1);
  for (int i = 0; i < n; ++i) {
    const float x = ds * static_cast<float>(i);
    t.x_m[i] = x;
    if (use_lane) {
      t.y_m[i] = lat_blend_alpha(x, p.traj_blend_m) * lat_poly_y(x, c0, c1, c2, c3);
    } else {
      t.y_m[i] = 0.0f;
    }
  }
  return t;
}

inline void plan_fill_speed(LatTraj& t, float v_ego, bool lead_valid, float d, float rel,
                            float lat, float D_see, bool lane_ok) {
  const PlanCal& p = plan_cal();
  const int n = std::min(kLatTrajPoints, std::max(2, p.traj_n));
  for (int i = 0; i < n; ++i) {
    t.v_mps[i] = plan_v_at_s(t.x_m[i], v_ego, lead_valid, d, rel, lat, D_see, lane_ok);
  }
}

}  // namespace gf_octave_planning
