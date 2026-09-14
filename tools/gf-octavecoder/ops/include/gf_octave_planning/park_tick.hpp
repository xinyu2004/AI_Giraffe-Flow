#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>

namespace gf_octave_planning {

constexpr int kParkTrajPoints = 32;
constexpr int kParkFsSectors = 36;

struct ParkTickOut {
  std::uint8_t valid{0};
  std::uint8_t n{0};
  float x[kParkTrajPoints]{};
  float y[kParkTrajPoints]{};
  float yaw[kParkTrajPoints]{};
};

/** True if (x,y) is inside near-field FS sector clearance (margin inward). */
inline bool park_fs_ok(float x, float y, const float* d_occ_m, float margin_m) {
  if (!d_occ_m) return true;
  const float r = std::sqrt(x * x + y * y);
  if (r < 0.2f) return true;
  float a = std::atan2(y, x);
  if (a < 0.0f) a += 6.2831853f;
  const int sec =
      static_cast<int>(a / 6.2831853f * static_cast<float>(kParkFsSectors)) % kParkFsSectors;
  return r + margin_m <= d_occ_m[sec];
}

/** Corresponds to octave_planning/parking/m_park_tick.m (geometric + FS clip). */
inline ParkTickOut m_park_tick(float slot_x, float slot_y, float slot_yaw, float /*slot_len*/,
                               float /*slot_wid*/, bool free, bool confirmed,
                               const float* d_occ_m = nullptr) {
  ParkTickOut out{};
  if (!confirmed || !free) {
    return out;
  }
  constexpr int n = 16;
  constexpr float kMargin = 0.6f;
  int kept = 0;
  for (int i = 0; i < n; ++i) {
    const float a = static_cast<float>(i) / static_cast<float>(std::max(n - 1, 1));
    const float x = a * slot_x;
    const float y = a * slot_y;
    const float yaw = a * slot_yaw;
    if (!park_fs_ok(x, y, d_occ_m, kMargin)) {
      break;
    }
    out.x[kept] = x;
    out.y[kept] = y;
    out.yaw[kept] = yaw;
    ++kept;
  }
  if (kept < 2) {
    return out;
  }
  out.n = static_cast<std::uint8_t>(kept);
  out.valid = 1;
  return out;
}

}  // namespace gf_octave_planning
