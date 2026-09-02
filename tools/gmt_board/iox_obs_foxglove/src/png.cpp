#include "gf_foxglove/png.hpp"

#include <zlib.h>

#include <cstdint>
#include <cstring>
#include <string>
#include <vector>

namespace gf_foxglove {
namespace {

void be32(std::string& o, std::uint32_t v) {
  o.push_back(static_cast<char>((v >> 24) & 0xff));
  o.push_back(static_cast<char>((v >> 16) & 0xff));
  o.push_back(static_cast<char>((v >> 8) & 0xff));
  o.push_back(static_cast<char>(v & 0xff));
}

void chunk(std::string& o, const char tag[4], const void* data, std::uint32_t n) {
  be32(o, n);
  o.append(tag, 4);
  if (n && data) o.append(static_cast<const char*>(data), n);
  uLong crc = crc32(0L, reinterpret_cast<const Bytef*>(tag), 4);
  if (n && data) crc = crc32(crc, reinterpret_cast<const Bytef*>(data), n);
  be32(o, static_cast<std::uint32_t>(crc));
}

constexpr char kB64[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

}  // namespace

std::string png_rgb(int width, int height, const std::uint8_t* rgb) {
  if (width <= 0 || height <= 0 || !rgb) return {};
  std::vector<std::uint8_t> raw(static_cast<std::size_t>(height) * (1 + width * 3));
  for (int y = 0; y < height; ++y) {
    raw[static_cast<std::size_t>(y) * (1 + width * 3)] = 0;
    std::memcpy(raw.data() + static_cast<std::size_t>(y) * (1 + width * 3) + 1,
                rgb + static_cast<std::size_t>(y) * width * 3,
                static_cast<std::size_t>(width) * 3);
  }
  uLongf zlen = compressBound(static_cast<uLong>(raw.size()));
  std::vector<std::uint8_t> z(zlen);
  if (compress2(z.data(), &zlen, raw.data(), static_cast<uLong>(raw.size()), 6) != Z_OK) {
    return {};
  }
  z.resize(zlen);

  std::string ihdr;
  be32(ihdr, static_cast<std::uint32_t>(width));
  be32(ihdr, static_cast<std::uint32_t>(height));
  ihdr.push_back(8);
  ihdr.push_back(2);
  ihdr.push_back(0);
  ihdr.push_back(0);
  ihdr.push_back(0);

  std::string out;
  out.append("\x89PNG\r\n\x1a\n", 8);
  chunk(out, "IHDR", ihdr.data(), static_cast<std::uint32_t>(ihdr.size()));
  chunk(out, "IDAT", z.data(), static_cast<std::uint32_t>(z.size()));
  chunk(out, "IEND", nullptr, 0);
  return out;
}

std::string b64_encode(const void* data, std::size_t n) {
  const auto* p = static_cast<const std::uint8_t*>(data);
  std::string o;
  o.reserve((n + 2) / 3 * 4);
  std::size_t i = 0;
  while (i + 3 <= n) {
    std::uint32_t v = (p[i] << 16) | (p[i + 1] << 8) | p[i + 2];
    o.push_back(kB64[(v >> 18) & 63]);
    o.push_back(kB64[(v >> 12) & 63]);
    o.push_back(kB64[(v >> 6) & 63]);
    o.push_back(kB64[v & 63]);
    i += 3;
  }
  if (i < n) {
    std::uint32_t v = p[i] << 16;
    if (i + 1 < n) v |= p[i + 1] << 8;
    o.push_back(kB64[(v >> 18) & 63]);
    o.push_back(kB64[(v >> 12) & 63]);
    if (i + 1 < n) {
      o.push_back(kB64[(v >> 6) & 63]);
      o.push_back('=');
    } else {
      o.push_back('=');
      o.push_back('=');
    }
  }
  return o;
}

}  // namespace gf_foxglove
