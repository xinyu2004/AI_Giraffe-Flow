// 环视感知（ADC 行泊一体）— 模块工程师只交 hpp
#pragma once

#include <cstdint>

namespace gf::demo::perception_surround {

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

struct SurroundObstacle {
  uint8_t id;
  uint8_t type;
  float x_m;
  float y_m;
  float heading_deg;
  float confidence;
};

struct SurroundWorld {
  uint64_t timestamp_ns;
  uint8_t obstacle_count;
  SurroundObstacle obstacles[32];
  uint8_t freepsace_valid;  // 示意：是否有可行驶区域摘要
};

}  // namespace gf::demo::perception_surround
