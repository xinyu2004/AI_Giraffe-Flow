#pragma once

#include "gf_octave_planning/clamp.hpp"

#include <cmath>

// Corresponds to octave_planning/afc/m_lat_lka.m
namespace gf_octave_planning {

inline constexpr float kSteerKy = 0.35f;
inline constexpr float kSteerKpsi = 0.80f;
inline constexpr float kMaxSteer = 0.55f;

/** Lane-center lateral + heading → CARLA steer (y>0 left; steer>0 right). */
inline float lat_steer_from_lane(float e_y, float c1) {
  float e = clamp(e_y, -1.8f, 1.8f);
  float ky = kSteerKy;
  const float ae = std::fabs(e);
  if (ae > 1.2f) {
    ky *= 0.35f;
  } else if (ae > 0.6f) {
    ky *= 0.55f;
  }
  const float c1c = clamp(c1, -0.5f, 0.5f);
  const float cmd = -ky * e - kSteerKpsi * c1c;
  return clamp(cmd, -kMaxSteer, kMaxSteer);
}

/** No usable LH: hold steer (do not mirror ego wheel after spin). */
inline float lat_steer_from_ego(float /*steer_angle_deg*/) {
  return 0.0f;
}

/** Orchestrator. */
inline float m_lat_lka(bool lane_valid, float e_y, float c1, float steer_angle_deg) {
  if (lane_valid) {
    return lat_steer_from_lane(e_y, c1);
  }
  return lat_steer_from_ego(steer_angle_deg);
}

}  // namespace gf_octave_planning
