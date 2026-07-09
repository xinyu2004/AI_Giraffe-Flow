// SOA Perception sheet (app.xlsx) → 泊车感知模块输入/输出
// synthesize: gf-codegen synthesize module --from-hpp io_types.hpp --meta module.meta.yaml

#pragma once

#include <cstdint>

namespace gf::demo::perception_parking {

// --- requires（订阅的 semantic 类型，与 Platform/DBC 侧对齐）---

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

struct VehicleModeStatus {
  uint8_t apa_on_off;
  uint8_t apa_mode;
  uint8_t apa_status;
  uint8_t avm_on_off;
  uint8_t avm_mode;
};

// --- provides（泊车感知输出）---

struct ParkingSlot {
  uint8_t slot_id;
  float p0_x_m;
  float p0_y_m;
  float p1_x_m;
  float p1_y_m;
  float p2_x_m;
  float p2_y_m;
};

struct VisionObstacle {
  uint8_t id;
  float confidence;
  uint8_t type;
  float heading_deg;
};

struct ParkingWorld {
  uint64_t timestamp_ns;
  uint8_t slot_count;
  ParkingSlot slots[6];
  uint16_t pdc_zone_mask;
  uint8_t uss_nearest_cm;
};

}  // namespace gf::demo::perception_parking
