#include "gf_channel/gf_channel.h"

#include <cstdio>
#include <cstring>
#include <vector>

int main() {
  const char* slot = "gf.channel.smoke";
  const uint32_t w = 16;
  const uint32_t h = 16;
  const uint16_t fmt = GF_CHANNEL_FMT_NV12;
  const uint32_t need = gf_channel_plane_bytes(fmt, w, h);
  if (need == 0) {
    std::fprintf(stderr, "plane_bytes=0\n");
    return 1;
  }

  GfChannel* wr = gf_channel_create(slot, w, h, fmt, 2);
  if (!wr) {
    std::perror("gf_channel_create");
    return 1;
  }
  GfChannel* rd = gf_channel_open(slot);
  if (!rd) {
    std::perror("gf_channel_open");
    gf_channel_close(wr);
    return 1;
  }

  std::vector<uint8_t> plane(need, 0x5a);
  if (gf_channel_publish(wr, plane.data(), need, 123456789ull, 1) != 0) {
    std::perror("gf_channel_publish");
    gf_channel_close(rd);
    gf_channel_close(wr);
    return 1;
  }

  std::vector<uint8_t> out(need, 0);
  uint64_t last = 0;
  uint64_t ts = 0;
  uint32_t ow = 0;
  uint32_t oh = 0;
  uint32_t plane_out_bytes = 0;
  uint16_t ofmt = 0;
  const int got = gf_channel_latest(rd, out.data(), need, &plane_out_bytes, &last, &ts,
                                &ow, &oh, &ofmt);
  if (got != 1 || last != 1 || ow != w || oh != h || plane_out_bytes != need) {
    std::fprintf(stderr, "latest fail got=%d last=%llu\n", got,
                 static_cast<unsigned long long>(last));
    gf_channel_close(rd);
    gf_channel_close(wr);
    return 1;
  }
  if (std::memcmp(out.data(), plane.data(), need) != 0) {
    std::fprintf(stderr, "plane mismatch\n");
    gf_channel_close(rd);
    gf_channel_close(wr);
    return 1;
  }
  if (gf_channel_latest(rd, out.data(), need, &plane_out_bytes, &last, &ts, &ow, &oh,
                    &ofmt) != 0) {
    std::fprintf(stderr, "expected no new frame\n");
    gf_channel_close(rd);
    gf_channel_close(wr);
    return 1;
  }

  gf_channel_close(rd);
  gf_channel_close(wr);
  std::printf("gf_channel_channel_smoke OK\n");
  return 0;
}
