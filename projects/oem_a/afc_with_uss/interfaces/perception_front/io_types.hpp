// OEM A / AFC+USS — 前视感知语义接口（gf-config 导入用）
// 输入订阅：EgoMotion（gateway）、UssZones（sensing.uss）— 本文件不重复定义
#pragma once

#include <cstdint>

namespace gf::demo::perception_front {

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
  FrontObject objects[20];
};

}  // namespace gf::demo::perception_front
