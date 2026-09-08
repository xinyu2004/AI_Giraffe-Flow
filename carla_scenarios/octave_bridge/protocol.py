"""TCP framing shared with giraffe_client / gf_carla_io (cosim_protocol.h)."""

from __future__ import annotations

import struct
from typing import Optional

GF_CH_VEHICLE_STATE_MAGIC = 0x47565354
GF_CH_VEHICLE_CMD_MAGIC = 0x4756434D
GF_CH_FAKE_PERC_MAGIC = 0x47465043
GF_CH_POD_VERSION = 1
GF_CHANNEL_FMT_NV12 = 0

GF_COSIM_MAGIC = 0x4743494D
GF_COSIM_VERSION = 2
GF_COSIM_MSG_HELLO = 1
GF_COSIM_MSG_HEARTBEAT = 2
GF_COSIM_MSG_VEHICLE_STATE = 10
GF_COSIM_MSG_FAKE_PERC = 11
GF_COSIM_MSG_CAMERA_NV12 = 12
GF_COSIM_MSG_VEHICLE_CMD = 20
GF_COSIM_SLOT_ID_LEN = 32
GF_COSIM_DEFAULT_PORT = 7600

FRAME_HDR = struct.Struct("<IHHIQQ")
assert FRAME_HDR.size == 28

CAM_HDR = struct.Struct("<IIHH32s")
assert CAM_HDR.size == 44

VS = struct.Struct("<IHHQfffB3x")
assert VS.size == 32

CMD = struct.Struct("<IHHQQfffffBB2x")
assert CMD.size == 48

# Same layout as carla_scenarios/src/lib/_fake_perc_pack.py
_OBJ = struct.Struct("<BBBB6f")
assert _OBJ.size == 28
_MAX_OBJ = 13
_MAX_ADJ = 4
_FP_HEAD = struct.Struct(
    "<"
    "IHH"
    "QQ"
    "BBBB"
    "ffff"
    "BBBB"
    "fff"
    "ffffffff"
    "BBBB"
    "B3x"
    "4B"
    "4f4f4f"
    "4B"
)
assert _FP_HEAD.size == 156
FP_V1_SIZE = _FP_HEAD.size + _MAX_OBJ * _OBJ.size
assert FP_V1_SIZE == 520
_TSR = struct.Struct("<HBB2f")  # name, relevancy, id, long, lat
# SIL: bit15 of name = minimum → Sup1 e_minimum (27)
_NAME_MIN_FLAG = 0x8000
E_MINIMUM_SUP1 = 27
_STAT = struct.Struct("<BBBB5f")
_TAIL_HEAD = struct.Struct("<BB2x")
_MAX_TSR = 6
_MAX_STAT = 6
FP_SIZE = FP_V1_SIZE + _TAIL_HEAD.size + _MAX_TSR * _TSR.size + _MAX_STAT * _STAT.size
assert FP_SIZE == 740


def pack_frame(msg_type: int, payload: bytes, ts: int, seq: int) -> bytes:
    hdr = FRAME_HDR.pack(
        GF_COSIM_MAGIC,
        GF_COSIM_VERSION,
        msg_type,
        len(payload),
        ts & 0xFFFFFFFFFFFFFFFF,
        seq & 0xFFFFFFFFFFFFFFFF,
    )
    return hdr + payload


def unpack_frame_hdr(buf: bytes) -> tuple[int, int, int, int, int, int]:
    return FRAME_HDR.unpack(buf)


def pack_cmd(
    *,
    seq: int,
    timestamp_ns: int,
    throttle: float,
    brake: float,
    steer: float,
    target_speed_mps: float,
    speed_mps: float,
    ctrl_mode: int,
    lane_code: int = 0,
) -> bytes:
    return CMD.pack(
        GF_CH_VEHICLE_CMD_MAGIC,
        GF_CH_POD_VERSION,
        0,
        timestamp_ns & 0xFFFFFFFFFFFFFFFF,
        seq & 0xFFFFFFFFFFFFFFFF,
        float(throttle),
        float(brake),
        float(steer),
        float(target_speed_mps),
        float(speed_mps),
        int(ctrl_mode) & 0xFF,
        int(lane_code) & 0xFF,
    )


def unpack_vehicle_state(blob: bytes) -> Optional[dict]:
    if len(blob) < VS.size:
        return None
    magic, ver, _res, ts, spd, yaw, steer, gear = VS.unpack_from(blob)
    if magic != GF_CH_VEHICLE_STATE_MAGIC or ver != GF_CH_POD_VERSION:
        return None
    return {
        "timestamp_ns": int(ts),
        "speed_mps": float(spd),
        "yaw_rate_degps": float(yaw),
        "steer_angle_deg": float(steer),
        "gear": int(gear),
    }


def unpack_fake_perc(blob: bytes) -> Optional[dict]:
    if len(blob) < FP_V1_SIZE:
        return None
    f = _FP_HEAD.unpack_from(blob)
    magic, ver = f[0], f[1]
    if magic != GF_CH_FAKE_PERC_MAGIC or ver not in (1, 2):
        return None
    # indices mirror _FP_HEAD.pack order in _fake_perc_pack.py
    i = 2
    _res = f[i]
    i += 1
    ts = f[i]
    i += 1
    seq = f[i]
    i += 1
    valid = f[i]
    i += 1
    lead_valid = f[i]
    i += 1
    lane_count = f[i]
    i += 1
    ego_lane_index = f[i]
    i += 1
    lead_distance_m = f[i]
    i += 1
    lead_rel_speed_mps = f[i]
    i += 1
    lead_lat_m = f[i]
    i += 1
    lead_heading_rad = f[i]
    i += 1
    lead_lane_assignment = f[i]
    i += 1
    lane_avail = f[i]
    i += 1
    host_left_type = f[i]
    i += 1
    host_right_type = f[i]
    i += 1
    lane_width_m = f[i]
    i += 1
    lane_conf = f[i]
    i += 1
    lane_vr_end_m = f[i]
    i += 1
    host_left_c0 = f[i]
    i += 1
    host_right_c0 = f[i]
    i += 1
    host_c1 = f[i]
    i += 1
    host_c2 = f[i]
    i += 1
    host_left_c1 = f[i]
    i += 1
    host_right_c1 = f[i]
    i += 1
    host_left_c2 = f[i]
    i += 1
    host_right_c2 = f[i]
    i += 1
    adj_n = f[i]
    i += 1
    dyn_n = f[i]
    i += 1
    vd_count = f[i]
    i += 1
    ped_count = f[i]
    i += 1
    cipv_id = f[i]
    i += 1
    # pad0 skipped in unpack? B3x is in struct after cipv — already consumed as part of pack
    # After cipv_id we have B3x then 4B adj_side — _FP_HEAD has "B3x" then "4B"
    # struct unpack includes pad as separate? "B3x" means 1 byte + 3 pad — only B is in tuple
    # Actually struct: "BBBB" "B3x" — wait look at format again:
    # "BBBB" = adj_n, dyn_n, vd_count, ped_count
    # "B3x" = cipv_id + 3 pad
    # So after ped_count comes cipv_id only (pad not in values)
    adj_side = list(f[i : i + 4])
    i += 4
    adj_c0 = list(f[i : i + 4])
    i += 4
    adj_c1 = list(f[i : i + 4])
    i += 4
    adj_c2 = list(f[i : i + 4])
    i += 4
    adj_type = list(f[i : i + 4])
    i += 4

    objs = []
    off = _FP_HEAD.size
    n_obj = min(_MAX_OBJ, int(dyn_n))
    for _ in range(n_obj):
        oid, cls, assign, is_ped, lon, lat, hdg, ln, wd, rel = _OBJ.unpack_from(blob, off)
        off += _OBJ.size
        objs.append(
            {
                "id": int(oid),
                "cls": int(cls),
                "assign": int(assign),
                "is_ped": int(is_ped),
                "long_m": float(lon),
                "lat_m": float(lat),
                "heading_rad": float(hdg),
                "len_m": float(ln),
                "wid_m": float(wd),
                "rel_v_mps": float(rel),
            }
        )

    out = {
        "valid": int(valid),
        "timestamp_ns": int(ts),
        "seq": int(seq),
        "lead_valid": int(lead_valid),
        "lane_count": int(lane_count),
        "ego_lane_index_from_left": int(ego_lane_index),
        "lead_distance_m": float(lead_distance_m),
        "lead_rel_speed_mps": float(lead_rel_speed_mps),
        "lead_lat_m": float(lead_lat_m),
        "lead_heading_rad": float(lead_heading_rad),
        "lead_lane_assignment": int(lead_lane_assignment),
        "lane_avail": int(lane_avail),
        "host_left_type": int(host_left_type),
        "host_right_type": int(host_right_type),
        "lane_width_m": float(lane_width_m),
        "lane_conf": float(lane_conf),
        "lane_vr_end_m": float(lane_vr_end_m),
        "host_left_c0": float(host_left_c0),
        "host_right_c0": float(host_right_c0),
        "host_c1": float(host_c1),
        "host_c2": float(host_c2),
        "host_left_c1": float(host_left_c1),
        "host_right_c1": float(host_right_c1),
        "host_left_c2": float(host_left_c2),
        "host_right_c2": float(host_right_c2),
        "adj_n": int(adj_n),
        "dyn_n": int(dyn_n),
        "vd_count": int(vd_count),
        "ped_count": int(ped_count),
        "cipv_id": int(cipv_id),
        "adj_side": [int(x) for x in adj_side],
        "adj_c0": [float(x) for x in adj_c0],
        "adj_c1": [float(x) for x in adj_c1],
        "adj_c2": [float(x) for x in adj_c2],
        "adj_type": [int(x) for x in adj_type],
        "obj": objs,
        "tsr": [],
        "stat": [],
        "tsr_n": 0,
        "stat_n": 0,
    }
    if ver >= 2 and len(blob) >= FP_SIZE:
        tsr_n, stat_n = _TAIL_HEAD.unpack_from(blob, FP_V1_SIZE)
        tsr_n = min(_MAX_TSR, int(tsr_n))
        stat_n = min(_MAX_STAT, int(stat_n))
        tsr_off = FP_V1_SIZE + _TAIL_HEAD.size
        tsrs = []
        for i in range(tsr_n):
            name, rel, tid, lon, lat = _TSR.unpack_from(blob, tsr_off + i * _TSR.size)
            wire = int(name)
            tsrs.append(
                {
                    "name": int(wire & 0x7FFF),
                    "sup1": E_MINIMUM_SUP1 if (wire & _NAME_MIN_FLAG) else 0,
                    "rel": int(rel),
                    "id": int(tid),
                    "long_m": float(lon),
                    "lat_m": float(lat),
                }
            )
        stat_off = tsr_off + _MAX_TSR * _TSR.size
        stats = []
        for i in range(stat_n):
            sid, cls, assign, _pad, lon, lat, hdg, ln, wd = _STAT.unpack_from(
                blob, stat_off + i * _STAT.size
            )
            stats.append(
                {
                    "id": int(sid),
                    "cls": int(cls),
                    "assign": int(assign),
                    "long_m": float(lon),
                    "lat_m": float(lat),
                    "heading_rad": float(hdg),
                    "len_m": float(ln),
                    "wid_m": float(wd),
                }
            )
        out["tsr"] = tsrs
        out["stat"] = stats
        out["tsr_n"] = tsr_n
        out["stat_n"] = stat_n
    return out
