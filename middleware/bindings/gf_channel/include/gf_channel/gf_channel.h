#pragma once

#include <cstddef>
#include <cstdint>

#ifdef __cplusplus
extern "C" {
#endif

/* Pixel formats — keep in sync with frame_ingest pixel_format strings. */
enum GfChannelFormat {
  GF_CHANNEL_FMT_NV12 = 0,
  GF_CHANNEL_FMT_NV21 = 1,
  GF_CHANNEL_FMT_YUV422 = 2,
  GF_CHANNEL_FMT_YUV444 = 3,
  GF_CHANNEL_FMT_RGB8 = 4,
};

enum {
  GF_CHANNEL_MAGIC = 0x47464348u, /* 'GFCH' */
  GF_CHANNEL_VERSION = 1u,
  GF_CHANNEL_MAX_BUFFERS = 3u,
  GF_CHANNEL_SLOT_MAX = 64u,
};

typedef struct GfChannel GfChannel;

uint32_t gf_channel_plane_bytes(uint16_t format, uint32_t w, uint32_t h);
uint16_t gf_channel_format_from_name(const char* name);
const char* gf_channel_format_name(uint16_t format);

/*
 * Create (writer / ingest). buffers must be 2 or 3.
 * slot examples: "gf.channel.front".
 */
GfChannel* gf_channel_create(const char* slot, uint32_t w, uint32_t h, uint16_t format,
                             uint32_t buffers);
GfChannel* gf_channel_open(const char* slot);
void gf_channel_close(GfChannel* ch);
int gf_channel_publish(GfChannel* ch, const void* plane, uint32_t plane_bytes,
                       uint64_t timestamp_ns, uint64_t seq);
int gf_channel_latest(GfChannel* ch, void* plane_out, uint32_t plane_cap,
                      uint32_t* out_plane_bytes, uint64_t* inout_last_seq,
                      uint64_t* out_timestamp_ns, uint32_t* out_w, uint32_t* out_h,
                      uint16_t* out_format);
int gf_channel_info(const GfChannel* ch, uint32_t* out_w, uint32_t* out_h,
                    uint16_t* out_format, uint32_t* out_plane_bytes, uint32_t* out_buffers);


#ifdef __cplusplus
}
#endif
