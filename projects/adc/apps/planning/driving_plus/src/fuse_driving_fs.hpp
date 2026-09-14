#pragma once

#include <algorithm>
#include <cmath>

namespace gf_plan_fs {

struct FsDriving {
  float d_front_m{120.0f};
  float d_rear_m{40.0f};
  float d_left_m{40.0f};
  float d_right_m{40.0f};
  bool rear_left_free{true};
  bool rear_right_free{true};
  bool lane_change_candidate{false};  // P2: intent only (traj bit / HUD); no steer
};

// Forward clearance hint from FCM-style lead distance (pre-D_see).
inline float ForwardClearanceFromLead(bool has_lead, float lead_long_m, float cap_m) {
  if (!has_lead || lead_long_m < 0.5f) {
    return cap_m;
  }
  return std::min(cap_m, std::max(0.0f, lead_long_m));
}

// Fuse FCM forward slice with surround near-field FS (driving pre-process only).
template <typename NearFs>
inline FsDriving FuseDrivingFs(float forward_clear_m, const NearFs* near) {
  FsDriving out;
  out.d_front_m = forward_clear_m;
  if (!near || !near->valid) {
    return out;
  }
  out.d_rear_m = near->d_rear_m;
  out.d_left_m = near->d_left_m;
  out.d_right_m = near->d_right_m;
  // Side-rear free if clearance beyond ~6 m in that quarter.
  out.rear_left_free = near->d_rear_m > 6.0f && near->d_left_m > 3.0f;
  out.rear_right_free = near->d_rear_m > 6.0f && near->d_right_m > 3.0f;
  out.lane_change_candidate = out.rear_left_free || out.rear_right_free;
  // Front takes the tighter of FCM forward vs surround front sector.
  out.d_front_m = std::min(out.d_front_m, near->d_front_m > 0.5f ? near->d_front_m : out.d_front_m);
  return out;
}

}  // namespace gf_plan_fs
