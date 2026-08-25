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
  const float cmd = -kSteerKy * e_y - kSteerKpsi * c1;
  return clamp(cmd, -kMaxSteer, kMaxSteer);
}

/** Fallback when LH invalid: map ego steer angle. */
inline float lat_steer_from_ego(float steer_angle_deg) {
  return clamp(steer_angle_deg / 25.0f, -1.0f, 1.0f);
}

/** Orchestrator. */
inline float m_lat_lka(bool lane_valid, float e_y, float c1, float steer_angle_deg) {
  if (lane_valid) {
    return lat_steer_from_lane(e_y, c1);
  }
  return lat_steer_from_ego(steer_angle_deg);
}

}  // namespace gf_octave_planning
