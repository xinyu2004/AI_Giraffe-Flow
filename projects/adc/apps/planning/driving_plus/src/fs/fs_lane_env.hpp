#pragma once

// Lane envelope helpers (bands / LC corridor). Strip intersect retired — Empty180 L1.

#include "fs/fs_types.hpp"
#include "fs/fs_lane_clear.hpp"

#include <algorithm>
#include <cmath>

namespace gf_plan_fs {

enum class LaneEnvMode : int {
  UnionAll = 0,
  HostOnly = 1,
  HostLeft = 2,
  HostRight = 3,
};

struct LcCorridor {
  bool valid{false};
  bool ready{false};
  RoadEdgePoly left{};
  RoadEdgePoly right{};
  float s_end_m{0.0f};
};

/** Corridor = committed S band (host ∪ target). side 0 → not ready. */
inline LcCorridor LcCorridorFromS(const LaneBands& bands, int side, float s_end_m) {
  LcCorridor c{};
  if (side == 0 || !bands.host_l.valid || !bands.host_r.valid) {
    return c;
  }
  if (side > 0) {
    if (!bands.have_left || !bands.left_outer.valid) {
      return c;
    }
    c.left = bands.left_outer;
    c.right = bands.host_r;
  } else {
    if (!bands.have_right || !bands.right_outer.valid) {
      return c;
    }
    c.left = bands.host_l;
    c.right = bands.right_outer;
  }
  c.valid = true;
  c.ready = true;
  c.s_end_m = std::max(0.0f, s_end_m);
  return c;
}

inline bool LaneEnvYAtX(const LaneBands& bands, LaneEnvMode mode, float x, float* y_hi,
                        float* y_lo) {
  if (!y_hi || !y_lo || !bands.host_l.valid || !bands.host_r.valid) {
    return false;
  }
  const float xq = x;
  float hl = RoadEdgeY(bands.host_l, xq);
  float hr = RoadEdgeY(bands.host_r, xq);
  if (hr > hl) {
    std::swap(hr, hl);
  }
  float top = hl;
  float bot = hr;
  auto widen_left = [&]() {
    if (bands.have_left && bands.left_outer.valid) {
      const float lo = RoadEdgeY(bands.left_outer, xq);
      top = std::max(top, std::max(lo, hl));
    }
  };
  auto widen_right = [&]() {
    if (bands.have_right && bands.right_outer.valid) {
      const float ro = RoadEdgeY(bands.right_outer, xq);
      bot = std::min(bot, std::min(ro, hr));
    }
  };
  switch (mode) {
    case LaneEnvMode::HostOnly:
      break;
    case LaneEnvMode::HostLeft:
      widen_left();
      break;
    case LaneEnvMode::HostRight:
      widen_right();
      break;
    case LaneEnvMode::UnionAll:
    default:
      widen_left();
      widen_right();
      break;
  }
  if (top < bot + 0.4f) {
    return false;
  }
  *y_hi = top;
  *y_lo = bot;
  return true;
}

}  // namespace gf_plan_fs
