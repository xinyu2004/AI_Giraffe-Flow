// Nullmax.xlsx → 行车感知模块输入/输出（--from-hpp 路径）
// synthesize: gf-codegen synthesize module --from-hpp io_types.hpp --meta module.meta.yaml

#pragma once

#include <cstdint>

namespace gf::demo::perception_driving {

struct EgoMotion {
  uint64_t timestamp_ns;
  float speed_mps;
  float yaw_rate_degps;
  float steer_angle_deg;
  uint8_t gear;
  float wheel_speed_fl_mps;
  float wheel_speed_fr_mps;
  float wheel_speed_rl_mps;
  float wheel_speed_rr_mps;
};

struct DrivingObject {
  uint8_t sync_id;
  uint8_t object_id;
  uint8_t object_class;
  float width_m;
  float length_m;
  float long_dist_m;
  float lat_dist_m;
  float rel_long_vel_mps;
  float rel_lat_vel_mps;
  float heading_rad;
  float existence_prob;
  uint8_t motion_status;
};

struct DrivingObjectList {
  uint8_t sync_id;
  uint8_t count;
  uint8_t cipv_id;
  DrivingObject objects[10];
};

}  // namespace gf::demo::perception_driving
