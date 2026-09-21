#pragma once

#include "gf_foxglove/bev_compose.hpp"

namespace gf_foxglove {

// Fill LiveBevState from a generated iceoryx sample. short_name is the SOR leaf
// (EgoMotion / Trajectory / ParkingTrajectory / UssZones / Perception_MESSAGE_Out_St /
//  FreespaceNear / Freespace / SurroundWorld when present).
// Display only — no fusion. ADC driving paints Freespace; parking paints Near.
void apply_sample(LiveBevState& st, const char* short_name, const void* sample);

}  // namespace gf_foxglove
