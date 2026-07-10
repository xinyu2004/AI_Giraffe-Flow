// OEM A / AFC+USS — 外仓（或外包）交付的前视接口落盘
// 本文件在「项目可见面」：源码仓不可见时，集成侧只持有此 hpp
// AFC+USS SKU 定制：本 SKU 固定订阅 UssZones，objects 容量按 AFC 标定

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
  FrontObject objects[20];  // AFC+USS 定制：相对共享基线 16 → 20
};

}  // namespace gf::demo::perception_front
