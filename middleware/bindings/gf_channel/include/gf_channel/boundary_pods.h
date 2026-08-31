#pragma once

/* Fixed POD layouts for GfChannel BLOB slots (host boundary ↔ Giraffe). */
#include <cstdint>

#ifdef __cplusplus
extern "C" {
#endif

enum {
  GF_CH_VEHICLE_STATE_MAGIC = 0x47565354u, /* 'GVST' */
  GF_CH_VEHICLE_CMD_MAGIC = 0x4756434du,   /* 'GVCM' */
  GF_CH_FAKE_PERC_MAGIC = 0x47465043u,     /* 'GFPC' */
  GF_CH_POD_VERSION = 1u,                 /* vehicle_state / cmd */
  GF_CH_FAKE_PERC_VERSION = 2u,           /* v1=520 B head; v2=+TSR/STATIC tail */
  GF_CH_FAKE_PERC_V1_SIZE = 520u,
  GF_CH_FAKE_PERC_MAX_OBJ = 13u,
  GF_CH_FAKE_PERC_MAX_ADJ = 4u,
  GF_CH_FAKE_PERC_MAX_TSR = 6u,
  GF_CH_FAKE_PERC_MAX_STAT = 6u,
};

#pragma pack(push, 1)
typedef struct GfVehicleStatePod {
  uint32_t magic;
  uint16_t version;
  uint16_t reserved;
  uint64_t timestamp_ns;
  float speed_mps;
  float yaw_rate_degps;
  float steer_angle_deg;
  uint8_t gear;
  uint8_t pad[3];
} GfVehicleStatePod;

typedef struct GfVehicleCmdPod {
  uint32_t magic;
  uint16_t version;
  uint16_t reserved;
  uint64_t timestamp_ns;
  uint64_t seq;
  float throttle;
  float brake;
  float steer;
  float target_speed_mps;
  float speed_mps;
  uint8_t ctrl_mode; /* 0 cruise 1 acc 2 aeb 3 pullaway */
  uint8_t lane_code; /* 0 none 1 left 2 right */
  uint8_t pad[2];
} GfVehicleCmdPod;

typedef struct GfFakePercObj {
  uint8_t id;
  uint8_t cls;
  uint8_t assign;
  uint8_t is_ped;
  float long_m;
  float lat_m;
  float heading_rad;
  float len_m;
  float wid_m;
  float rel_v_mps;
} GfFakePercObj;

typedef struct GfFakePercTsr {
  uint16_t sign_name; /* DSTSR_Sign_Name */
  uint8_t relevancy;  /* DSTSR_Relevancy */
  uint8_t pad;
  float long_m;
  float lat_m;
} GfFakePercTsr;

typedef struct GfFakePercStat {
  uint8_t id;
  uint8_t cls;
  uint8_t assign;
  uint8_t pad;
  float long_m;
  float lat_m;
  float heading_rad;
  float len_m;
  float wid_m;
} GfFakePercStat;

typedef struct GfFakePercPod {
  uint32_t magic;
  uint16_t version;
  uint16_t reserved;
  uint64_t timestamp_ns;
  uint64_t seq;
  uint8_t valid; /* 1 = payload usable */
  uint8_t lead_valid;
  uint8_t lane_count;
  uint8_t ego_lane_index_from_left;
  float lead_distance_m;
  float lead_rel_speed_mps;
  float lead_lat_m;
  float lead_heading_rad;
  uint8_t lead_lane_assignment;
  uint8_t lane_avail;
  uint8_t host_left_type;
  uint8_t host_right_type;
  float lane_width_m;
  float lane_conf;
  float lane_vr_end_m;
  float host_left_c0;
  float host_right_c0;
  float host_c1;
  float host_c2;
  float host_left_c1;
  float host_right_c1;
  float host_left_c2;
  float host_right_c2;
  uint8_t adj_n;
  uint8_t dyn_n;
  uint8_t vd_count;
  uint8_t ped_count;
  uint8_t cipv_id;
  uint8_t pad0[3];
  uint8_t adj_side[GF_CH_FAKE_PERC_MAX_ADJ];
  float adj_c0[GF_CH_FAKE_PERC_MAX_ADJ];
  float adj_c1[GF_CH_FAKE_PERC_MAX_ADJ];
  float adj_c2[GF_CH_FAKE_PERC_MAX_ADJ];
  uint8_t adj_type[GF_CH_FAKE_PERC_MAX_ADJ];
  GfFakePercObj obj[GF_CH_FAKE_PERC_MAX_OBJ];
  /* v2 tail — ignored when version==1 or payload is 520 B */
  uint8_t tsr_n;
  uint8_t stat_n;
  uint8_t pad1[2];
  GfFakePercTsr tsr[GF_CH_FAKE_PERC_MAX_TSR];
  GfFakePercStat stat[GF_CH_FAKE_PERC_MAX_STAT];
} GfFakePercPod;
#pragma pack(pop)

#ifdef __cplusplus
}
#endif
