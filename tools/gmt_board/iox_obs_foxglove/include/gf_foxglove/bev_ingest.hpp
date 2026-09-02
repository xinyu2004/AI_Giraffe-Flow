#pragma once

#include "gf_foxglove/bev_compose.hpp"

namespace gf_foxglove {

// Fill LiveBevState from a generated iceoryx sample. short_name is the SOR leaf
// (EgoMotion / Trajectory / UssZones / Perception_MESSAGE_Out_St).
void apply_sample(LiveBevState& st, const char* short_name, const void* sample);

}  // namespace gf_foxglove
