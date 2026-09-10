// OEM A / AFC+USS — 行车规划语义接口（gf-config 导入用）
#pragma once

#include <cstdint>

namespace gf::demo::planning_driving {

struct Trajectory {
  uint64_t timestamp_ns;
  uint8_t point_count;
  float points_x_m[60];
  float points_y_m[60];
  float points_v_mps[60];  // v4 plan speed along path (BEV); 0 if unused
  uint8_t gear_shift_first;
  uint8_t gear_shift_second;
  // Actuator command co-published with path (iceoryx; no planning_ctrl.json).
  float throttle;
  float brake;
  float steer;
  float target_speed_mps;
  uint8_t ctrl_mode;  // 0=cruise 1=acc 2=aeb (label only; v4 not a state machine)
  // Process curves (ME semantics) — Live plots these, not Sign_Name[0] / Obj[0].
  float D_see_m;
  float s_stop_m;
  float cipv_long_m;
  float cipv_rel_v;
  // Active Relevant DSTSR speed limits (mps). 0 = none. Not vis v_cap.
  float v_sign_max_mps;
  float v_sign_min_mps;
};

}  // namespace gf::demo::planning_driving
