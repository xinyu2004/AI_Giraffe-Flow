#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>

namespace gf_octave_planning {

constexpr int kParkTrajPoints = 32;

struct ParkTickOut {
  std::uint8_t valid{0};
  std::uint8_t n{0};
  float x[kParkTrajPoints]{};
  float y[kParkTrajPoints]{};
  float yaw[kParkTrajPoints]{};
};

/** Corresponds to octave_planning/parking/m_park_tick.m (geometric stub; A* later). */
inline ParkTickOut m_park_tick(float slot_x, float slot_y, float slot_yaw, float /*slot_len*/,
                               float /*slot_wid*/, bool free, bool confirmed) {
  ParkTickOut out{};
  if (!confirmed || !free) {
    return out;
  }
  constexpr int n = 16;
  for (int i = 0; i < n; ++i) {
    const float a = static_cast<float>(i) / static_cast<float>(std::max(n - 1, 1));
    out.x[i] = a * slot_x;
    out.y[i] = a * slot_y;
    out.yaw[i] = a * slot_yaw;
  }
  out.n = static_cast<std::uint8_t>(n);
  out.valid = 1;
  return out;
}

}  // namespace gf_octave_planning
