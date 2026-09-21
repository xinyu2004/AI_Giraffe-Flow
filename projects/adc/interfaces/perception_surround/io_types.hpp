#pragma once
#include <cstdint>

namespace gf::demo::perception_surround {

/** FAPA-aligned FSD boundary semantic (IPC_APA_FSD_TPYE). */
enum class FsBoundType : uint8_t {
  Unknown = 0,
  Car = 1,
  Bicycle = 2,
  Pedestrian = 3,
  Obstacle = 4,
  Pillar = 5,
  Building = 6,
  Curb = 7,
  Optical = 8,
  LaneBound = 9,
};

struct SurroundObject {
  uint8_t object_id;
  uint8_t object_class;  // IPC_APAOT_* style
  float long_dist_m;
  float lat_dist_m;
  float rel_vel_long_mps;
  float length_m;
  float width_m;
  float heading_rad;
};

struct ParkingSlot {
  uint8_t slot_id;
  float center_x_m;
  float center_y_m;
  float yaw_rad;
  float length_m;
  float width_m;
  uint8_t free;
  uint8_t slot_type;  // IPC_SLOTTYPE_*
};

// Surround / parking perception Out. Objects + slots (FAPA OD/PLD extract).
struct SurroundWorld {
  uint64_t timestamp_ns;
  uint8_t n_obj;
  SurroundObject objects[16];
  uint8_t n_slot;
  ParkingSlot slots[8];
};

// Near-field Empty180 (FAPA w_points style). +x forward, +y left; bin i at (i+0.5)*2°.
struct FreespaceNear {
  uint64_t timestamp_ns;
  float d_r_m[180];
  uint8_t type[180];
  uint8_t valid;
};

}  // namespace gf::demo::perception_surround
