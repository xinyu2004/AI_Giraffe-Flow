#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace gf_foxglove {

// RGB8 PNG (zlib), 1:1 with gf_gmt.adas_scenarios._png_rgb.
std::string png_rgb(int width, int height, const std::uint8_t* rgb);

std::string b64_encode(const void* data, std::size_t n);

}  // namespace gf_foxglove
