#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>

namespace gf_surround {

inline constexpr int kFsSectors = 36;
// Envelope (ADC truth / near FS): rear 周视, side 环视; front is FCM-owned.
inline constexpr float kFsRearCapM = 40.0f;
inline constexpr float kFsSideCapM = 10.0f;
inline constexpr float kFsFwdCapM = 15.0f;  // near-only overlap; not 120 m front
inline constexpr float kObjHalfW = 0.9f;

struct ObjSample {
  float long_dist_m;
  float lat_dist_m;
};

/** Cap for sector mid-angle: +x forward, +y left. */
inline float SectorCapM(int sec) {
  const float twopi = 6.2831853f;
  const float ang = (static_cast<float>(sec) + 0.5f) * (twopi / kFsSectors);
  const float c = std::cos(ang);
  const float s = std::sin(ang);
  if (c < -0.15f) {
    return kFsRearCapM;  // rearward 周视
  }
  if (std::fabs(s) > 0.55f) {
    return kFsSideCapM;  // left/right 环视
  }
  return kFsFwdCapM;
}

// Near-field FS from object samples (vehicle frame: +x fwd, +y left).
template <typename FsOut>
inline void ComputeFreespaceNear(const ObjSample* objs, int n_obj, std::uint64_t ts_ns,
                                 FsOut* fs) {
  if (!fs) {
    return;
  }
  *fs = {};
  fs->timestamp_ns = ts_ns;
  fs->valid = 1;
  for (int i = 0; i < kFsSectors; ++i) {
    fs->d_occ_m[i] = SectorCapM(i);
  }
  fs->d_front_m = kFsFwdCapM;
  fs->d_rear_m = kFsRearCapM;
  fs->d_left_m = kFsSideCapM;
  fs->d_right_m = kFsSideCapM;

  const float twopi = 6.2831853f;
  const int n = n_obj < 0 ? 0 : n_obj;
  for (int i = 0; i < n; ++i) {
    const float x = objs[i].long_dist_m;
    const float y = objs[i].lat_dist_m;
    const float r = std::sqrt(x * x + y * y);
    if (r < 0.3f) {
      continue;
    }
    float a = std::atan2(y, x);
    if (a < 0.0f) {
      a += twopi;
    }
    const int sec = static_cast<int>(a / twopi * kFsSectors) % kFsSectors;
    const float clear = std::max(0.0f, r - kObjHalfW);
    fs->d_occ_m[sec] = std::min(fs->d_occ_m[sec], clear);

    if (x >= 0.0f && std::fabs(y) < 2.0f) {
      fs->d_front_m = std::min(fs->d_front_m, clear);
    }
    if (x < 0.0f && std::fabs(y) < 2.0f) {
      fs->d_rear_m = std::min(fs->d_rear_m, clear);
    }
    if (y >= 0.0f && std::fabs(x) < 4.0f) {
      fs->d_left_m = std::min(fs->d_left_m, clear);
    }
    if (y < 0.0f && std::fabs(x) < 4.0f) {
      fs->d_right_m = std::min(fs->d_right_m, clear);
    }
  }
}

}  // namespace gf_surround
