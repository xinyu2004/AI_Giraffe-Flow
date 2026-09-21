#pragma once

// Per-lane forward clear (LC foundation). Independent of Empty/Clip/Occupy.

#include "fs/fs_types.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>

namespace gf_plan_fs {

enum class LaneSlot : int { Host = 0, Left = 1, Right = 2, None = -1 };

struct LaneBands {
  RoadEdgePoly host_l{};
  RoadEdgePoly host_r{};
  RoadEdgePoly left_outer{};
  RoadEdgePoly right_outer{};
  bool have_left{false};
  bool have_right{false};
};

struct LaneClearFwd {
  float host_m{kFsFrontFarCapM};
  float left_m{kFsFrontFarCapM};
  float right_m{kFsFrontFarCapM};
  float rear_m{gf_fs_envelope::kFsRearCapM};  // behind ego; shapes rear tip
  int n_host{0};
  int n_left{0};
  int n_right{0};
  int n_rear{0};
  bool have_left{false};
  bool have_right{false};
};

struct LaneClearSample {
  float x_m{0.0f};
  float y_m{0.0f};
  float half_l_m{2.0f};
  float half_w_m{0.9f};
  std::uint8_t assign{0};
  std::uint8_t cls{0};
  std::uint16_t id{0};
  bool hard_world{false};
};

struct LaneAssignConflict {
  std::uint16_t id{0};
  LaneSlot geom{LaneSlot::None};
  LaneSlot assign{LaneSlot::None};
};

inline bool InBandBetween(float y, float a, float b, float pad = 0.15f) {
  const float lo = std::min(a, b) - pad;
  const float hi = std::max(a, b) + pad;
  return y >= lo && y <= hi;
}

inline LaneSlot ClassifyLaneGeom(float x, float y, const LaneBands& b) {
  if (!b.host_l.valid || !b.host_r.valid) {
    return LaneSlot::None;
  }
  const float hl = RoadEdgeY(b.host_l, x);
  const float hr = RoadEdgeY(b.host_r, x);
  if (InBandBetween(y, hl, hr)) {
    return LaneSlot::Host;
  }
  if (b.have_left && b.left_outer.valid) {
    const float lo = RoadEdgeY(b.left_outer, x);
    if (InBandBetween(y, lo, hl)) {
      return LaneSlot::Left;
    }
  }
  if (b.have_right && b.right_outer.valid) {
    const float ro = RoadEdgeY(b.right_outer, x);
    if (InBandBetween(y, hr, ro)) {
      return LaneSlot::Right;
    }
  }
  return LaneSlot::None;
}

inline LaneSlot AssignHintToSlot(std::uint8_t assign) {
  if (assign == 3) {
    return LaneSlot::Host;
  }
  if (assign == 2 || assign == 1) {
    return LaneSlot::Left;
  }
  if (assign == 4 || assign == 5) {
    return LaneSlot::Right;
  }
  return LaneSlot::None;
}

inline bool BandOverlapsY(float y0, float y1, float a, float b, float pad = 0.15f) {
  const float lo = std::min(a, b) - pad;
  const float hi = std::max(a, b) + pad;
  return y1 >= lo && y0 <= hi;
}

inline void ClipLaneBumper(LaneClearFwd* out, LaneSlot slot, float bumper) {
  if (!out) {
    return;
  }
  if (slot == LaneSlot::Host) {
    out->host_m = std::min(out->host_m, bumper);
    ++out->n_host;
  } else if (slot == LaneSlot::Left && out->have_left) {
    out->left_m = std::min(out->left_m, bumper);
    ++out->n_left;
  } else if (slot == LaneSlot::Right && out->have_right) {
    out->right_m = std::min(out->right_m, bumper);
    ++out->n_right;
  }
}

inline LaneClearFwd ComputeLaneClearFwd(const LaneBands& bands, const LaneClearSample* objs,
                                        int n_obj, float cap_m = kFsFrontFarCapM,
                                        LaneAssignConflict* conflicts = nullptr,
                                        int* n_conflicts = nullptr, int max_conflicts = 0) {
  LaneClearFwd out;
  out.have_left = bands.have_left;
  out.have_right = bands.have_right;
  const float cap = std::max(1.0f, std::min(kFsFrontFarCapM, cap_m));
  out.host_m = cap;
  out.left_m = cap;
  out.right_m = cap;
  out.rear_m = gf_fs_envelope::kFsRearCapM;
  if (n_conflicts) {
    *n_conflicts = 0;
  }
  if (!objs || n_obj <= 0) {
    return out;
  }
  for (int i = 0; i < n_obj; ++i) {
    const LaneClearSample& o = objs[i];
    // Behind ego: only shortens rear tip. Never clips forward host/left/right clear
    // (that caused right-front retract with only a rear-side vehicle).
    if (o.x_m < 0.5f) {
      // Host lane only. A rear-side / neighbor box must not pull the global rear tip
      // (same class as the old right-front retract).
      const float xq = o.x_m < 0.0f ? 0.0f : o.x_m;
      const LaneSlot slot = ClassifyLaneGeom(xq, o.y_m, bands);
      const bool host = (slot == LaneSlot::Host) ||
                        (!bands.host_l.valid && std::fabs(o.y_m) < 1.9f);
      if (host) {
        const float near_face = o.x_m + std::max(0.5f, o.half_l_m);
        const float dist_behind = std::max(0.5f, -near_face);
        if (dist_behind + 0.25f < out.rear_m) {
          out.rear_m = dist_behind;
          ++out.n_rear;
        }
      }
      continue;
    }
    const float bumper = std::max(0.5f, o.x_m - std::max(0.5f, o.half_l_m));
    const LaneSlot geom = ClassifyLaneGeom(o.x_m, o.y_m, bands);
    const LaneSlot hint = AssignHintToSlot(o.assign);
    if (hint != LaneSlot::None && geom != LaneSlot::None && hint != geom && conflicts &&
        n_conflicts && *n_conflicts < max_conflicts) {
      LaneAssignConflict& c = conflicts[(*n_conflicts)++];
      c.id = o.id;
      c.geom = geom;
      c.assign = hint;
    }
    if (o.hard_world && bands.host_l.valid && bands.host_r.valid) {
      const float y0 = o.y_m - std::max(0.2f, o.half_w_m);
      const float y1 = o.y_m + std::max(0.2f, o.half_w_m);
      const float hl = RoadEdgeY(bands.host_l, o.x_m);
      const float hr = RoadEdgeY(bands.host_r, o.x_m);
      if (BandOverlapsY(y0, y1, hl, hr)) {
        ClipLaneBumper(&out, LaneSlot::Host, bumper);
      }
      if (bands.have_left && bands.left_outer.valid) {
        const float lo = RoadEdgeY(bands.left_outer, o.x_m);
        if (BandOverlapsY(y0, y1, lo, hl)) {
          ClipLaneBumper(&out, LaneSlot::Left, bumper);
        }
      }
      if (bands.have_right && bands.right_outer.valid) {
        const float ro = RoadEdgeY(bands.right_outer, o.x_m);
        if (BandOverlapsY(y0, y1, hr, ro)) {
          ClipLaneBumper(&out, LaneSlot::Right, bumper);
        }
      }
      continue;
    }
    ClipLaneBumper(&out, geom, bumper);
  }
  return out;
}

}  // namespace gf_plan_fs
