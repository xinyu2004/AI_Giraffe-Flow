#pragma once

#include "gf_foxglove/bev_compose.hpp"

#include <string_view>

namespace gf_foxglove {

// Apply one tap-style NDJSON object:
//   {"topic":"/gf/EgoMotion","t_ns":…,"data":{…}}
// or {"topic":"…","data":{…}} with timestamp inside data.
// Returns true if topic was recognized (even if fields were sparse).
bool apply_ndjson_row(LiveBevState& st, std::string_view line);

}  // namespace gf_foxglove
