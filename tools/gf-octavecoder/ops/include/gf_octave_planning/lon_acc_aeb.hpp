#pragma once

#include "gf_octave_planning/clamp.hpp"

#include <algorithm>
#include <cmath>

// Corresponds to octave_planning/afc/m_lon_acc_aeb.m (+ helpers).
// Independent functions for reuse; keep semantics 1:1 with .m gold.

namespace gf_octave_planning {

struct LonCtrl {
  float throttle{0.35f};
  float brake{0.0f};
  float target_speed_mps{12.0f};
  const char* mode{"cruise"};
};

/** No lead: cruise / standstill pull-away throttle floor (CARLA start). */
inline LonCtrl lon_cruise(float v) {
  LonCtrl c{};
  c.mode = "cruise";
  c.target_speed_mps = 12.0f;
  const float err = c.target_speed_mps - v;
  if (v < 0.8f) {
    c.throttle = clamp(0.45f + err * 0.05f, 0.40f, 0.75f);
    c.brake = 0.0f;
  } else {
    c.throttle = clamp(0.2f + err * 0.08f, 0.0f, 0.7f);
    c.brake = (err < -2.0f) ? clamp((-err - 2.0f) * 0.1f, 0.0f, 0.4f) : 0.0f;
  }
  return c;
}

/** Hard AEB when closing on a near threat. */
inline LonCtrl lon_aeb(float v, float d, float ttc) {
  LonCtrl c{};
  c.mode = "aeb";
  c.target_speed_mps = 0.0f;
  c.throttle = 0.0f;
  c.brake = (d < 5.0f || ttc < 1.0f) ? 1.0f
                                      : clamp(0.55f + (10.0f - d) * 0.05f, 0.55f, 1.0f);
  (void)v;
  return c;
}

/** Stopped with safe gap → accelerate toward follow/cruise. */
inline LonCtrl lon_pullaway(float v, float d, float rel, float gap_err) {
  LonCtrl c{};
  c.mode = "pullaway";
  const float pull = clamp(8.0f + gap_err * 0.2f + rel * 0.3f, 6.0f, 12.0f);
  c.target_speed_mps = pull;
  c.throttle = clamp(0.42f + (pull - v) * 0.06f, 0.35f, 0.75f);
  c.brake = 0.0f;
  (void)d;
  return c;
}

/** ACC gap follow. */
inline LonCtrl lon_acc_follow(float v, float d, float rel) {
  LonCtrl c{};
  c.mode = "acc";
  const float desired_gap = clamp(std::max(8.0f, v * 1.6f), 8.0f, 40.0f);
  const float gap_err = d - desired_gap;
  c.target_speed_mps = clamp(v + gap_err * 0.15f + rel * 0.4f, 0.0f, 16.0f);
  const float speed_err = c.target_speed_mps - v;
  if (speed_err >= 0.0f) {
    c.throttle = clamp(0.15f + speed_err * 0.1f, 0.0f, 0.65f);
    c.brake = 0.0f;
  } else {
    c.throttle = 0.0f;
    c.brake = clamp((-speed_err) * 0.12f, 0.0f, 0.7f);
  }
  return c;
}

/** Orchestrator — same branching as legacy ComputeAccAeb (longitudinal only). */
inline LonCtrl m_lon_acc_aeb(float v, bool lead_valid, float d, float rel) {
  v = std::max(0.0f, v);
  if (!lead_valid) {
    return lon_cruise(v);
  }
  const float closing = std::max(0.0f, -rel);
  const float ttc = (closing > 0.5f) ? (d / closing) : 1.0e6f;
  if (d < 5.0f || (v > 1.2f && (d < 10.0f || ttc < 1.4f))) {
    return lon_aeb(v, d, ttc);
  }
  const float desired_gap = clamp(std::max(8.0f, v * 1.6f), 8.0f, 40.0f);
  const float gap_err = d - desired_gap;
  if (v < 1.0f && d > 10.0f) {
    return lon_pullaway(v, d, rel, gap_err);
  }
  return lon_acc_follow(v, d, rel);
}

}  // namespace gf_octave_planning
