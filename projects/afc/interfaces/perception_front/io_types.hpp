// 前视感知（AFC / ADC 行车主路径）— 模块工程师只交 hpp
#pragma once

#include <cstdint>

namespace gf::demo::perception_front {

struct EgoMotion {
  uint64_t timestamp_ns;
  float speed_mps;
  float yaw_rate_degps;
  float steer_angle_deg;
  uint8_t gear;
};

// 可选订阅（AFC+USS / ADC）；形状与 uss_sensing::UssZones 对齐
struct UssZones {
  uint64_t timestamp_ns;
  uint8_t sys_status;
  uint8_t nearest_cm;
  uint16_t zone_mask;
};

struct FrontObject {
  uint8_t object_id;
  uint8_t object_class;
  float long_dist_m;
  float lat_dist_m;
  float rel_long_vel_mps;
  float rel_lat_vel_mps;
  float existence_prob;
};

struct FrontObjectList {
  uint64_t timestamp_ns;
  uint8_t count;
  uint8_t cipv_id;
  FrontObject objects[16];
};

}  // namespace gf::demo::perception_front
