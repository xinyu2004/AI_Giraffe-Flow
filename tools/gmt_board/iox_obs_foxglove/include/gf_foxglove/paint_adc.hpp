#pragma once

#include "gf_foxglove/bev_compose.hpp"

#include <string>

namespace gf_foxglove {

/** ADC BEV paint entry (forces ADC window / FS stitch path). */
std::string paint_adc_bev(const LiveBevState& st, int width = kBevW, int height = kBevH);

}  // namespace gf_foxglove
