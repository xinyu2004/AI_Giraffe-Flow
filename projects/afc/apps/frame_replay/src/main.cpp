// gf_frame_replay — independent module: replay NV12 planes into camera GfChannel.
// Reads GF_REPLAY_DIR/plane_%06llu.nv12 or a single GF_CARLA_FRAME_PATH raw file cycling.

#include "gf_channel/gf_channel.h"

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
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

bool ReadFile(const std::string& path, std::vector<std::uint8_t>* out) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    return false;
  }
  in.seekg(0, std::ios::end);
  const auto n = static_cast<std::size_t>(in.tellg());
  in.seekg(0, std::ios::beg);
  out->resize(n);
  in.read(reinterpret_cast<char*>(out->data()), static_cast<std::streamsize>(n));
  return static_cast<std::size_t>(in.gcount()) == n;
}

}  // namespace

int main() {
  signal(SIGINT, OnSig);
  signal(SIGTERM, OnSig);

  const char* slot = EnvOr("GF_CAMERA_SLOT", "gf.channel.front");
  const std::uint32_t w = static_cast<std::uint32_t>(std::atoi(EnvOr("GF_CARLA_CAM_W", "640")));
  const std::uint32_t h = static_cast<std::uint32_t>(std::atoi(EnvOr("GF_CARLA_CAM_H", "480")));
  const std::uint32_t need = gf_channel_plane_bytes(GF_CHANNEL_FMT_NV12, w, h);
  const char* replay_dir = std::getenv("GF_REPLAY_DIR");
  const char* single = EnvOr("GF_CARLA_FRAME_PATH", "");

  GfChannel* ch = gf_channel_open(slot);
  if (!ch) {
    std::cerr << "[ERROR] gf_frame_replay: open " << slot << " failed\n";
    return 2;
  }

  std::cout << "gf_frame_replay: " << slot << " need=" << need << "\n";
  std::vector<std::uint8_t> plane(need, 16);
  std::uint64_t seq = 0;
  while (!g_stop) {
    bool ok = false;
    if (replay_dir && replay_dir[0]) {
      char path[512];
      std::snprintf(path, sizeof(path), "%s/plane_%06llu.nv12", replay_dir,
                    static_cast<unsigned long long>(seq));
      std::vector<std::uint8_t> tmp;
      if (ReadFile(path, &tmp) && tmp.size() >= need) {
        std::memcpy(plane.data(), tmp.data(), need);
        ok = true;
      } else if (seq > 0) {
        seq = 0;
        continue;
      }
    } else if (single && single[0]) {
      std::vector<std::uint8_t> tmp;
      if (ReadFile(single, &tmp) && tmp.size() >= need) {
        std::memcpy(plane.data(), tmp.data(), need);
        ok = true;
      }
    }
    if (!ok) {
      static bool logged_skip = false;
      if (!logged_skip) {
        std::cerr << "[ERROR] gf_frame_replay: no plane file; not publishing "
                     "(no gray keep-alive)\n";
        logged_skip = true;
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(40));
      continue;
    }
    (void)gf_channel_publish(ch, plane.data(), need, now_ns(), seq);
    ++seq;
    std::this_thread::sleep_for(std::chrono::milliseconds(40));
  }
  gf_channel_close(ch);
  return 0;
}
