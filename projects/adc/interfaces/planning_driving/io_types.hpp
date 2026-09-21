// OEM A / AFC+USS — 行车规划语义接口（gf-config 导入用）
#pragma once

#include <cstdint>

namespace gf::demo::planning_driving {

struct Trajectory {
  uint64_t timestamp_ns;
  uint8_t point_count;
  float points_x_m[60];
  float points_y_m[60];
  float points_v_mps[60];
  uint8_t gear_shift_first;
  uint8_t gear_shift_second;
  float throttle;
  float brake;
  float steer;
  float target_speed_mps;
  uint8_t ctrl_mode;
  float D_see_m;
  float s_stop_m;
  float cipv_long_m;
  float cipv_rel_v;
  float v_sign_max_mps;
  float v_sign_min_mps;
};

// Driving fused drivability. Acceptance = Empty180 Pack (≤180 rim points).
struct Freespace {
  uint64_t timestamp_ns;
  float d_lane_fwd_m[3];
  uint8_t n_poly;
  float poly_x_m[180];
  float poly_y_m[180];
  uint8_t valid;
};

}  // namespace gf::demo::planning_driving
