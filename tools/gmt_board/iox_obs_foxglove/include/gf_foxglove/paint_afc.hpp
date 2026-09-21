#pragma once

#include "gf_foxglove/bev_compose.hpp"

#include <string>

namespace gf_foxglove {

/** AFC BEV paint entry (forces AFC window / D_see path). */
std::string paint_afc_bev(const LiveBevState& st, int width = kBevW, int height = kBevH);

}  // namespace gf_foxglove
