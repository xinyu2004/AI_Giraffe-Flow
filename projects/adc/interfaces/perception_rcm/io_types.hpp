#pragma once
#include <cstdint>

namespace gf::demo::perception_rcm {

// Rear Camera Module (RCM) — FCM 小集 for lane-change.
// Keep: host/adj lanes + dynamic objects (+ velocity).
// Drop: TSR / signs / HLB / LRE / AF / FailSafe FS / … (front FCM only).

struct RcmLane {
  float c0_m;
  float c1_rad;
  float c2;
  float c3;
  float view_range_m;
  uint8_t quality;  // 0..3
  uint8_t side;     // 0=hostL 1=hostR 2=adjL 3=adjR …
};

struct RcmObject {
  uint8_t object_id;
  uint8_t object_class;
  float long_dist_m;       // +x forward (rear cam: typically negative in ego)
  float lat_dist_m;        // +y left
  float rel_vel_long_mps;
  float rel_vel_lat_mps;
  float abs_vel_mps;
};

struct Perception_Rear_Out_St {
  uint64_t timestamp_ns;
  uint8_t valid;  // 1 = sample OK when published (empty scene still 1); silence ⇒ unhealthy
  uint8_t n_lane;
  RcmLane lanes[8];
  uint8_t n_obj;
  RcmObject objects[16];
};

}  // namespace gf::demo::perception_rcm
