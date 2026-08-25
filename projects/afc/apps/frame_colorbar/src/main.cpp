// gf_frame_colorbar — independent module: synthesize NV12 into camera GfChannel.

#include "gf_channel/gf_channel.h"

#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

#include <signal.h>

namespace {

volatile sig_atomic_t g_stop = 0;
void OnSig(int) { g_stop = 1; }

const char* EnvOr(const char* k, const char* fb) {
  const char* v = std::getenv(k);
  return (v && v[0]) ? v : fb;
}

std::uint64_t now_ns() {
  return static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(
          std::chrono::steady_clock::now().time_since_epoch())
          .count());
}

void FillNv12(std::vector<std::uint8_t>* plane, std::uint32_t w, std::uint32_t h,
              std::uint64_t seq) {
  const std::size_t y_sz = static_cast<std::size_t>(w) * h;
  const std::size_t uv_sz = y_sz / 2;
  plane->assign(y_sz + uv_sz, 0);
  const std::uint8_t yv = static_cast<std::uint8_t>(16 + (seq * 3) % 220);
  std::memset(plane->data(), yv, y_sz);
  std::memset(plane->data() + y_sz, 128, uv_sz);
  // Moving bar
  const std::uint32_t bar = static_cast<std::uint32_t>((seq * 4) % w);
  for (std::uint32_t row = h / 3; row < 2 * h / 3; ++row) {
    for (std::uint32_t col = 0; col < 8 && bar + col < w; ++col) {
      (*plane)[row * w + bar + col] = 235;
    }
  }
}

}  // namespace

int main() {
  signal(SIGINT, OnSig);
  signal(SIGTERM, OnSig);

  const char* slot = EnvOr("GF_CAMERA_SLOT", "gf.channel.front");
  const std::uint32_t w = static_cast<std::uint32_t>(std::atoi(EnvOr("GF_CARLA_CAM_W", "640")));
  const std::uint32_t h = static_cast<std::uint32_t>(std::atoi(EnvOr("GF_CARLA_CAM_H", "480")));

  GfChannel* ch = gf_channel_open(slot);
  if (!ch) {
    std::cerr << "[ERROR] gf_frame_colorbar: open " << slot << " failed errno=" << errno
              << " (ingest must Create first)\n";
    return 2;
  }

  std::cout << "gf_frame_colorbar: writing " << slot << " " << w << "x" << h << "\n";
  std::vector<std::uint8_t> plane;
  std::uint64_t seq = 0;
  while (!g_stop) {
    FillNv12(&plane, w, h, seq);
    if (gf_channel_publish(ch, plane.data(), static_cast<std::uint32_t>(plane.size()), now_ns(),
                           seq) != 0) {
      std::cerr << "[ERROR] gf_frame_colorbar: publish failed\n";
      break;
    }
    ++seq;
    std::this_thread::sleep_for(std::chrono::milliseconds(33));
  }
  gf_channel_close(ch);
  return 0;
}
