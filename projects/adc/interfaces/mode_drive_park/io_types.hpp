#pragma once
#include <cstdint>

namespace gf::demo::mode_drive_park {

// Product drive/park mode (Mode Manager). Not an FG state.
// 0=Driving 1=SpotSearch 2=Parking
struct VehicleMode {
  uint64_t timestamp_ns;
  uint8_t mode;
  float speed_mps;
  uint8_t apa_armed;
  uint8_t slot_confirmed;
};

}  // namespace gf::demo::mode_drive_park
