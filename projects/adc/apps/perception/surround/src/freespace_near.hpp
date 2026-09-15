#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>

namespace gf_surround {

inline constexpr int kFsSectors = 36;
// Envelope (ADC): rear/side Near; front far = FCM + fused D_see within FOV.
// Distances / FOV: docs/zh/sku/adc/fs_fov_bev_scheme.md (gf-config unique).
inline constexpr float kFsRearCapM = 35.0f;
inline constexpr float kFsRearFovDeg = 120.0f;  // rear cal until dedicated rear mount
// Front optical wedge = camera_contract front.fov (default 100°).
inline constexpr float kFsFwdFovDeg = 100.0f;
inline constexpr float kFsSideCapM = 5.25f;  // ~1.5 × 3.5 m lane
inline constexpr float kFsFwdCapM = 15.0f;   // near-only; empty ≠ cut D_see
inline constexpr float kObjHalfW = 0.9f;

struct ObjSample {
  float long_dist_m;
  float lat_dist_m;
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

/** Rear 周视 wedge centered on −x. */
inline bool InRearFov(float ang_rad) {
  constexpr float pi = 3.14159265f;
  const float half = 0.5f * kFsRearFovDeg * (pi / 180.0f);
  return std::fabs(WrapPi(ang_rad - pi)) <= half;
}

/** Front windshield wedge centered on +x (= contract front.fov). */
inline bool InFrontFov(float ang_rad) {
  constexpr float pi = 3.14159265f;
  const float half = 0.5f * kFsFwdFovDeg * (pi / 180.0f);
  return std::fabs(WrapPi(ang_rad)) <= half;
}

/** Cap for sector mid-angle: +x forward, +y left. */
inline float SectorCapM(int sec) {
  const float twopi = 6.2831853f;
  const float ang = (static_cast<float>(sec) + 0.5f) * (twopi / kFsSectors);
  if (InFrontFov(ang)) {
    return kFsFwdCapM;  // near overlap only; paint/fuse extends with D_see
  }
  if (InRearFov(ang)) {
    return kFsRearCapM;
  }
  return kFsSideCapM;
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
    if (x < 0.0f && std::fabs(y) < 2.0f && InRearFov(a)) {
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
