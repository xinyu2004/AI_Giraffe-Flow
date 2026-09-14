#pragma once
#include <cstdint>

namespace gf::demo::perception_surround {

struct SurroundObject {
  uint8_t object_id;
  uint8_t object_class;
  float long_dist_m;
  float lat_dist_m;
  float rel_vel_long_mps;
};

struct ParkingSlot {
  uint8_t slot_id;
  float center_x_m;
  float center_y_m;
  float yaw_rad;
  float length_m;
  float width_m;
  uint8_t free;
};

// Stub surround / parking perception Out (stage A). Not FCM.
// Objects + slots; freespace is a separate Provide (FreespaceNear).
struct SurroundWorld {
  uint64_t timestamp_ns;
  uint8_t n_obj;
  SurroundObject objects[16];
  uint8_t n_slot;
  ParkingSlot slots[8];
};

// Near-field drivability from surround (not FailSafe Perception_FS_Out).
// Formal contract: fixed 36 sectors + axis clearances; densify later, do not rename.
struct FreespaceNear {
  uint64_t timestamp_ns;
  float d_occ_m[36];  // 10° sectors; +x forward, +y left
  float d_front_m;
  float d_rear_m;
  float d_left_m;
  float d_right_m;
  uint8_t valid;
};

}  // namespace gf::demo::perception_surround
