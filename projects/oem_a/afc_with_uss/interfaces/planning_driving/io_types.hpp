// OEM A / AFC+USS — 行车规划语义接口（gf-config 导入用）
#pragma once

#include <cstdint>

namespace gf::demo::planning_driving {

struct Trajectory {
  uint64_t timestamp_ns;
  uint8_t point_count;
  float points_x_m[60];
  float points_y_m[60];
  uint8_t gear_shift_first;
  uint8_t gear_shift_second;
};

}  // namespace gf::demo::planning_driving
