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
 * slot examples: "gf.channel.front" (compat: "gf.tip.front").
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

/* --- short-term tip_* aliases --- */
typedef GfChannel GfTipChannel;
typedef enum GfChannelFormat GfTipFormat;
#define GF_TIP_FMT_NV12 GF_CHANNEL_FMT_NV12
#define GF_TIP_FMT_NV21 GF_CHANNEL_FMT_NV21
#define GF_TIP_FMT_YUV422 GF_CHANNEL_FMT_YUV422
#define GF_TIP_FMT_YUV444 GF_CHANNEL_FMT_YUV444
#define GF_TIP_FMT_RGB8 GF_CHANNEL_FMT_RGB8
#define GF_TIP_MAGIC GF_CHANNEL_MAGIC
#define GF_TIP_VERSION GF_CHANNEL_VERSION
#define GF_TIP_MAX_BUFFERS GF_CHANNEL_MAX_BUFFERS
#define GF_TIP_SLOT_MAX GF_CHANNEL_SLOT_MAX
#define gf_tip_plane_bytes gf_channel_plane_bytes
#define gf_tip_format_from_name gf_channel_format_from_name
#define gf_tip_format_name gf_channel_format_name
#define gf_tip_create gf_channel_create
#define gf_tip_open gf_channel_open
#define gf_tip_close gf_channel_close
#define gf_tip_publish gf_channel_publish
#define gf_tip_latest gf_channel_latest
#define gf_tip_info gf_channel_info

#ifdef __cplusplus
}
#endif
