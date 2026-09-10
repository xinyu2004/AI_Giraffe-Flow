#pragma once

/* Cosim framing: giraffe_client (host) ↔ gf_carla_io (board/SIL).
 * Payload bodies reuse boundary_pods.h / raw NV12; multi-camera via slot_id. */

#include "gf_channel/boundary_pods.h"

#include <cstdint>

#ifdef __cplusplus
extern "C" {
#endif

enum {
  GF_COSIM_MAGIC = 0x4743494du, /* 'GCIM' */
  GF_COSIM_VERSION = 2u,        /* v2: camera hdr carries slot_id[32] */
  GF_COSIM_DEFAULT_PORT = 7600u,
  GF_COSIM_SLOT_ID_LEN = 32u,
};

enum {
  GF_COSIM_MSG_HELLO = 1,
  GF_COSIM_MSG_HEARTBEAT = 2,
  GF_COSIM_MSG_VEHICLE_STATE = 10,
  GF_COSIM_MSG_FAKE_PERC = 11,
  GF_COSIM_MSG_CAMERA_NV12 = 12,
  GF_COSIM_MSG_SURROUND_WORLD = 13,
  GF_COSIM_MSG_MODE_HINT = 14,
  GF_COSIM_MSG_VEHICLE_CMD = 20,
};

#pragma pack(push, 1)
typedef struct GfCosimFrameHdr {
  uint32_t magic;
  uint16_t version;
  uint16_t msg_type;
  uint32_t payload_len;
  uint64_t timestamp_ns;
  uint64_t seq;
} GfCosimFrameHdr;

/* CAMERA_NV12 payload = GfCosimCameraHdr + NV12 plane.
 * slot_id e.g. "front", "surround_left" → board opens/creates gf.channel.<slot_id>. */
typedef struct GfCosimCameraHdr {
  uint32_t width;
  uint32_t height;
  uint16_t format; /* GF_CHANNEL_FMT_NV12 */
  uint16_t reserved;
  char slot_id[GF_COSIM_SLOT_ID_LEN]; /* NUL-padded ASCII id */
} GfCosimCameraHdr;
#pragma pack(pop)

#ifdef __cplusplus
}
#endif
