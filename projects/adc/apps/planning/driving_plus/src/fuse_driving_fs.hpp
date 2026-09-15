#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>

namespace gf_plan_fs {

inline constexpr int kFsSectors = 36;
inline constexpr float kFwdFovDeg = 100.0f;   // camera_contract front.fov
inline constexpr float kRearFovDeg = 120.0f;
inline constexpr float kRearCapM = 35.0f;
inline constexpr float kSideCapM = 5.25f;
inline constexpr float kNearFwdEnvelopeM = 15.0f;
inline constexpr float kFwdCapM = 120.0f;

struct FsDriving {
  float d_front_m{120.0f};
  float d_rear_m{35.0f};
  float d_left_m{5.25f};
  float d_right_m{5.25f};
  bool rear_left_free{true};
  bool rear_right_free{true};
  bool lane_change_candidate{false};
};

inline float WrapPi(float a) {
  constexpr float pi = 3.14159265f;
  constexpr float twopi = 6.2831853f;
  while (a > pi) {
    a -= twopi;
  }
  while (a < -pi) {
    a += twopi;
  }
  return a;
}

inline bool InFrontFov(float ang_rad) {
  const float half = 0.5f * kFwdFovDeg * (3.14159265f / 180.0f);
  return std::fabs(WrapPi(ang_rad)) <= half;
}

inline bool InRearFov(float ang_rad) {
  constexpr float pi = 3.14159265f;
  const float half = 0.5f * kRearFovDeg * (pi / 180.0f);
  return std::fabs(WrapPi(ang_rad - pi)) <= half;
}

inline float ForwardClearanceFromLead(bool has_lead, float lead_long_m, float cap_m) {
  if (!has_lead || lead_long_m < 0.5f) {
    return cap_m;
  }
  return std::min(cap_m, std::max(0.0f, lead_long_m));
}

template <typename NearFs>
inline FsDriving FuseDrivingFs(float forward_clear_m, const NearFs* near) {
  FsDriving out;
  out.d_front_m = forward_clear_m;
  if (!near || !near->valid) {
    return out;
  }
  out.d_rear_m = std::min(kRearCapM, near->d_rear_m > 0.5f ? near->d_rear_m : kRearCapM);
  out.d_left_m = near->d_left_m > 0.5f ? near->d_left_m : kSideCapM;
  out.d_right_m = near->d_right_m > 0.5f ? near->d_right_m : kSideCapM;
  out.rear_left_free = out.d_rear_m > 6.0f && out.d_left_m > 3.0f;
  out.rear_right_free = out.d_rear_m > 6.0f && out.d_right_m > 3.0f;
  out.lane_change_candidate = out.rear_left_free || out.rear_right_free;
  if (near->d_front_m > 0.5f && near->d_front_m + 0.25f < kNearFwdEnvelopeM) {
    out.d_front_m = std::min(out.d_front_m, near->d_front_m);
  }
  return out;
}

// Three-segment driving Freespace. Empty Near front cap does not stay at 15 m.
template <typename NearFs, typename FsOut>
inline void ComposeFreespace(float d_front_m, const NearFs* near, std::uint64_t ts_ns,
                             FsOut* fs) {
  if (!fs) {
    return;
  }
  *fs = {};
  fs->timestamp_ns = ts_ns;
  fs->valid = 1;
  const float d_front = std::max(0.5f, std::min(kFwdCapM, d_front_m));
  const float twopi = 6.2831853f;
  float d_rear = kRearCapM;
  float d_left = kSideCapM;
  float d_right = kSideCapM;
  if (near && near->valid) {
    if (near->d_rear_m > 0.5f) {
      d_rear = std::min(kRearCapM, near->d_rear_m);
    }
    if (near->d_left_m > 0.5f) {
      d_left = near->d_left_m;
    }
    if (near->d_right_m > 0.5f) {
      d_right = near->d_right_m;
    }
  }
  fs->d_front_m = d_front;
  fs->d_rear_m = d_rear;
  fs->d_left_m = d_left;
  fs->d_right_m = d_right;

  for (int i = 0; i < kFsSectors; ++i) {
    const float ang = (static_cast<float>(i) + 0.5f) * (twopi / kFsSectors);
    float r = kSideCapM;
    if (InFrontFov(ang)) {
      r = d_front;
    } else if (InRearFov(ang)) {
      r = d_rear;
    }
    if (near && near->valid) {
      const float nr = near->d_occ_m[i];
      if (nr > 0.5f) {
        if (InFrontFov(ang)) {
          if (nr + 0.25f < kNearFwdEnvelopeM) {
            r = std::min(r, nr);
          }
        } else {
          r = std::min(r, nr);
        }
      }
    }
    fs->d_occ_m[i] = std::max(0.5f, r);
  }
}

}  // namespace gf_plan_fs
