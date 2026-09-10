#pragma once
#include <cstdint>

namespace gf::demo::planning_parking {

// Parking trajectory stub (stage A). Distinct from driving Trajectory for mode select.
struct ParkingTrajectory {
  uint64_t timestamp_ns;
  uint8_t valid;
  uint8_t n_points;
  float x_m[32];
  float y_m[32];
  float yaw_rad[32];
};

}  // namespace gf::demo::planning_parking
