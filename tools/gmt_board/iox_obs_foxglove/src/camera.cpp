#include "gf_foxglove/camera.hpp"

#include "gf_foxglove/png.hpp"
#include "gf_foxglove/ws_hub.hpp"

#include "gf_channel/gf_channel.h"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

namespace gf_foxglove {
namespace {

void nv12_preview(const std::uint8_t* yuv, int w, int h, bool swap_uv, int max_w,
                  std::vector<std::uint8_t>* rgb, int* nw, int* nh) {
  const int step = std::max(1, (w + max_w - 1) / max_w);
  *nw = std::max(1, w / step);
  *nh = std::max(1, h / step);
  rgb->assign(static_cast<std::size_t>(*nw) * *nh * 3, 0);
  const int y_sz = w * h;
  const std::uint8_t* y_plane = yuv;
  const std::uint8_t* uv = yuv + y_sz;
  auto clamp = [](int v) { return v < 0 ? 0 : v > 255 ? 255 : v; };
  for (int oy = 0; oy < *nh; ++oy) {
    const int sy = std::min(h - 1, oy * step);
    for (int ox = 0; ox < *nw; ++ox) {
      const int sx = std::min(w - 1, ox * step);
      const int yv = y_plane[sy * w + sx];
      const int ui = (sy / 2) * w + (sx & ~1);
      int u, v;
      if (swap_uv) {
        v = uv[ui];
        u = uv[ui + 1];
      } else {
        u = uv[ui];
        v = uv[ui + 1];
      }
      const int c = yv - 16, d = u - 128, e = v - 128;
      const std::size_t i = (static_cast<std::size_t>(oy) * *nw + ox) * 3;
      (*rgb)[i] = static_cast<std::uint8_t>(clamp((298 * c + 409 * e + 128) >> 8));
      (*rgb)[i + 1] = static_cast<std::uint8_t>(clamp((298 * c - 100 * d - 208 * e + 128) >> 8));
      (*rgb)[i + 2] = static_cast<std::uint8_t>(clamp((298 * c + 516 * d + 128) >> 8));
    }
  }
}

std::uint64_t wall_ns() {
  return static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(
          std::chrono::system_clock::now().time_since_epoch())
          .count());
}

}  // namespace

CameraPub::CameraPub(std::string slot, std::string frame_path)
    : slot_(std::move(slot)), frame_path_(std::move(frame_path)) {
  if (!frame_path_.empty()) {
    source_ = "file:" + frame_path_;
    ok_ = true;
    return;
  }
  ch_ = gf_channel_open(slot_.c_str());
  if (!ch_) {
    std::cerr << "gf-foxglove-ws: camera slot open failed " << slot_ << "\n";
    ok_ = false;
    source_ = slot_;
    return;
  }
  source_ = slot_;
  ok_ = true;
}

CameraPub::~CameraPub() {
  if (ch_) gf_channel_close(static_cast<GfChannel*>(ch_));
}

std::string CameraPub::poll(std::uint64_t* t_ns_out) {
  if (!ok_) return {};
  std::vector<std::uint8_t> plane;
  std::uint32_t nbytes = 0, w = 0, h = 0;
  std::uint16_t fmt = 0;
  std::uint64_t t_ns = 0;
  std::uint64_t seq = last_seq_;

  if (ch_) {
    plane.resize(1920 * 1080 * 3);
    const int rc = gf_channel_latest(static_cast<GfChannel*>(ch_), plane.data(),
                                     static_cast<std::uint32_t>(plane.size()), &nbytes, &seq, &t_ns,
                                     &w, &h, &fmt);
    if (rc != 0 || nbytes == 0 || w == 0 || h == 0) return {};
    if (seq == last_seq_) return {};
    last_seq_ = seq;
    plane.resize(nbytes);
  } else {
    std::ifstream in(frame_path_, std::ios::binary);
    if (!in) return {};
    in.seekg(0, std::ios::end);
    const auto sz = in.tellg();
    in.seekg(0);
    plane.resize(static_cast<std::size_t>(sz));
    in.read(reinterpret_cast<char*>(plane.data()), sz);
    // meta beside file is optional; treat as RGB preview 320x240 if unknown
    w = 320;
    h = 240;
    fmt = GF_CHANNEL_FMT_RGB8;
    t_ns = wall_ns();
  }

  std::vector<std::uint8_t> rgb;
  int pw = static_cast<int>(w), ph = static_cast<int>(h);
  if (fmt == GF_CHANNEL_FMT_NV12 || fmt == GF_CHANNEL_FMT_NV21) {
    nv12_preview(plane.data(), static_cast<int>(w), static_cast<int>(h), fmt == GF_CHANNEL_FMT_NV21,
                 320, &rgb, &pw, &ph);
  } else if (fmt == GF_CHANNEL_FMT_RGB8) {
    const int max_w = 640;
    if (static_cast<int>(w) > max_w) {
      const float scale = static_cast<float>(max_w) / static_cast<float>(w);
      pw = max_w;
      ph = std::max(1, static_cast<int>(h * scale));
      rgb.assign(static_cast<std::size_t>(pw) * ph * 3, 0);
      for (int y = 0; y < ph; ++y) {
        const int sy = std::min(static_cast<int>(h) - 1, static_cast<int>(y / scale));
        for (int x = 0; x < pw; ++x) {
          const int sx = std::min(static_cast<int>(w) - 1, static_cast<int>(x / scale));
          const std::size_t si = (static_cast<std::size_t>(sy) * w + sx) * 3;
          const std::size_t di = (static_cast<std::size_t>(y) * pw + x) * 3;
          rgb[di] = plane[si];
          rgb[di + 1] = plane[si + 1];
          rgb[di + 2] = plane[si + 2];
        }
      }
    } else {
      rgb.assign(plane.begin(), plane.begin() + static_cast<std::ptrdiff_t>(w) * h * 3);
    }
  } else {
    pw = static_cast<int>(w);
    ph = static_cast<int>(h);
    rgb.assign(static_cast<std::size_t>(pw) * ph * 3, 0);
    for (int i = 0; i < pw * ph && i < static_cast<int>(plane.size()); ++i) {
      rgb[i * 3] = rgb[i * 3 + 1] = rgb[i * 3 + 2] = plane[i];
    }
  }
  if (t_ns == 0) t_ns = wall_ns();
  if (t_ns_out) *t_ns_out = t_ns;
  const std::string png = png_rgb(pw, ph, rgb.data());
  if (png.empty()) return {};
  return compressed_image_json(t_ns, png, "driving_front");
}

}  // namespace gf_foxglove
