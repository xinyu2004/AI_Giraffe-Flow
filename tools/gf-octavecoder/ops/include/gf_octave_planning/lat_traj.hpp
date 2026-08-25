#pragma once

#include "gf_octave_planning/clamp.hpp"

#include <algorithm>
#include <cmath>

// Corresponds to octave_planning/afc/m_lat_traj.m — fixed-length path (L1).
namespace gf_octave_planning {

inline constexpr int kLatTrajPoints = 16;
inline constexpr float kBlendLenM = 18.0f;

struct LatTraj {
  float x_m[kLatTrajPoints]{};
  float y_m[kLatTrajPoints]{};
  float horizon_m{25.0f};
};

inline float lat_poly_y(float x, float c0, float c1, float c2, float c3) {
  return c0 + c1 * x + c2 * x * x + c3 * x * x * x;
}

inline float lat_blend_alpha(float x, float blend_len_m) {
  return 1.0f - std::exp(-x / blend_len_m);
}

/** Fill ego-frame lane-keep path (N=16). */
inline LatTraj m_lat_traj(float speed_mps, float speed_scale, bool lane_valid, float c0,
                          float c1, float c2, float c3, float x_end) {
  LatTraj t{};
  const float speed = std::max(speed_mps * speed_scale, 0.2f);
  const float x_cap = lane_valid ? x_end : 100.0f;
  t.horizon_m = clamp(speed * 4.0f, 25.0f, std::min(100.0f, x_cap));
  const float ds = t.horizon_m / static_cast<float>(kLatTrajPoints - 1);
  for (int i = 0; i < kLatTrajPoints; ++i) {
    const float x = ds * static_cast<float>(i);
    t.x_m[i] = x;
    if (lane_valid) {
      const float alpha = lat_blend_alpha(x, kBlendLenM);
      t.y_m[i] = alpha * lat_poly_y(x, c0, c1, c2, c3);
    } else {
      t.y_m[i] = 0.0f;
    }
  }
  return t;
}

}  // namespace gf_octave_planning
