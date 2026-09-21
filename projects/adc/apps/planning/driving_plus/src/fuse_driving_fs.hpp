#pragma once

// Facade: LC gate + FuseDrivingFs + Empty180 compose orch.

#include "fs/fs_types.hpp"
#include "fs/fs_lane_clear.hpp"
#include "fs/fs_lane_env.hpp"
#include "fs/fs_empty180.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>

namespace gf_plan_fs {

struct FsDriving {
  float d_front_m{kFsFrontFarCapM};
  float d_rear_m{gf_fs_envelope::kFsRearCapM};
  float d_left_m{gf_fs_envelope::kFsSideCapM};
  float d_right_m{gf_fs_envelope::kFsSideCapM};
  bool rear_left_free{false};
  bool rear_right_free{false};
  bool lane_change_candidate{false};
};

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
  FsEmpty180 a{};
  a.valid = true;
  for (int i = 0; i < kFsEmptyN; ++i) {
    a.r[i] = near->d_r_m[i];
    a.type[i] = near->type[i];
  }
  const float df = FsDfsFwdFromActive(a);
  out.d_rear_m = std::min(gf_fs_envelope::RearCapM(), FsAxisClear(a, -0.85f, 0.0f, true));
  out.d_left_m = FsLatClear(a, true);
  out.d_right_m = FsLatClear(a, false);
  if (df > 0.5f && df + 0.25f < kFsNearFrontCapM) {
    out.d_front_m = std::min(out.d_front_m, df);
  }
  out.rear_left_free = out.d_rear_m > 6.0f && out.d_left_m > 3.0f;
  out.rear_right_free = out.d_rear_m > 6.0f && out.d_right_m > 3.0f;
  out.lane_change_candidate = out.rear_left_free || out.rear_right_free;
  return out;
}

struct LcGate {
  bool ego_ok{false};
  bool near_ok{false};
  bool rcm_ok{false};
  bool corridor_ready{false};
  bool inhibit{true};

  const char* Reason() const {
    if (!ego_ok) {
      return "ego";
    }
    if (!near_ok) {
      return "near";
    }
    if (!rcm_ok) {
      return "rcm";
    }
    if (!corridor_ready) {
      return "corridor";
    }
    return "ok";
  }
};

inline LcGate MakeLcGate(bool ego_ok, bool near_ok, bool rcm_ok, bool corridor_ready = false) {
  LcGate g;
  g.ego_ok = ego_ok;
  g.near_ok = near_ok;
  g.rcm_ok = rcm_ok;
  g.corridor_ready = corridor_ready;
  g.inhibit = !(ego_ok && near_ok && rcm_ok && corridor_ready);
  return g;
}

inline void ApplyLcInhibit(FsDriving* fs, const LcGate& gate) {
  if (!fs || !gate.inhibit) {
    return;
  }
  fs->rear_left_free = false;
  fs->rear_right_free = false;
  fs->lane_change_candidate = false;
}

template <typename NearFs, typename FsOut>
inline void ComposeFreespace(float d_empty_cap_m, float /*lane_width_m*/, const NearFs* near,
                             const FsOccSample* objs, int n_obj, std::uint64_t ts_ns, FsOut* fs,
                             const FrontCamMount& /*cam*/ = FrontCamMount{},
                             const RoadEdgePoly& road_left = RoadEdgePoly{},
                             const RoadEdgePoly& road_right = RoadEdgePoly{},
                             const RoadEdgePoly* hard_walls = nullptr, int n_hard_walls = 0,
                             const LaneBands& /*bands*/ = LaneBands{},
                             const LaneClearFwd* lane_clear = nullptr,
                             LaneEnvMode /*env_mode*/ = LaneEnvMode::UnionAll,
                             const LcCorridor* /*lc*/ = nullptr) {
  FsComposeEmpty180(d_empty_cap_m, near, objs, n_obj, ts_ns, fs, road_left, road_right, hard_walls,
                    n_hard_walls, lane_clear);
}

}  // namespace gf_plan_fs
