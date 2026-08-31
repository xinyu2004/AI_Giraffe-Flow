"""Wire pods ↔ PlanningView / PlanningResult (semantic shield vs board Out/Ego/Trajectory).

Mapping rules mirror FCM FillLanesFromTruth / FillOutFromTruth so BEV feed matches board.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from . import protocol as P

CTRL_MODE_IDS = {"cruise": 0, "acc": 1, "aeb": 2, "pullaway": 3}
CTRL_MODE_NAMES = {v: k for k, v in CTRL_MODE_IDS.items()}

_VR_CAP = 130.0
_E_TRAFFIC_SIGNALS = 164
_E_STOP_AHEAD = 196


def _keep_adj(side: int) -> bool:
    # Display may include next-next (5/6). Refuse empty / unknown side.
    return side != 0


@dataclass
class EgoView:
    speed_mps: float = 0.0
    yaw_rate_degps: float = 0.0
    steer_angle_deg: float = 0.0
    gear: int = 4


@dataclass
class LaneLine:
    side: int = 0
    c0: float = 0.0
    c1: float = 0.0
    c2: float = 0.0
    c3: float = 0.0
    vr_start: float = 0.0
    vr_end: float = 0.0
    conf: float = 0.0
    avail: int = 0
    lanemark_type: int = 1


@dataclass
class DynObj:
    obj_id: int = 0
    obj_class: int = 0
    long_m: float = 0.0
    lat_m: float = 0.0
    rel_v_mps: float = 0.0
    heading_rad: float = 0.0
    len_m: float = 4.5
    wid_m: float = 1.8
    is_ped: int = 0
    assign: int = 3


@dataclass
class TsrItem:
    name: int = 0
    long_m: float = 0.0
    lat_m: float = 0.0
    relevancy: int = 0


@dataclass
class PercView:
    """≈ Perception_MESSAGE_Out semantic (filled from fake_perc today)."""

    host: list[LaneLine] = field(default_factory=list)
    adj: list[LaneLine] = field(default_factory=list)
    lane_width_m: float = 3.5
    objects: list[DynObj] = field(default_factory=list)
    static: list[DynObj] = field(default_factory=list)
    tsr: list[TsrItem] = field(default_factory=list)
    cipv_id: int = 0
    vd_count: int = 0
    ped_count: int = 0
    # planning shortcuts
    lead_valid: bool = False
    lead_distance_m: float = 0.0
    lead_rel_speed_mps: float = 0.0
    lead_lat_m: float = 0.0
    lead_heading_rad: float = 0.0
    lane_valid: bool = False
    e_y: float = 0.0
    c1: float = 0.0
    c0: float = 0.0
    c2: float = 0.0
    c3: float = 0.0
    x_end: float = 60.0
    lane_conf: float = 0.0
    lane_count: int = 0


@dataclass
class PlanningView:
    stamp_ns: int = 0
    seq: int = 0
    source: str = "fake_perc"
    ego: EgoView = field(default_factory=EgoView)
    perc: PercView = field(default_factory=PercView)


@dataclass
class PlanningResult:
    stamp_ns: int = 0
    seq: int = 0
    throttle: float = 0.0
    brake: float = 0.0
    steer: float = 0.0
    target_speed_mps: float = 0.0
    ctrl_mode: str = "cruise"
    points_x_m: list[float] = field(default_factory=list)
    points_y_m: list[float] = field(default_factory=list)
    points_v_mps: list[float] = field(default_factory=list)
    horizon_m: float = 25.0
    D_see_m: float = 0.0
    T_plan_s: float = 0.0
    allow_lc: int = 0
    lane_code: int = 0


def _fcm_style_perc(fp: dict[str, Any]) -> PercView:
    """Mirror projects/afc FCM FillLanesFromTruth + dyn fill (gold field names in bev rows)."""
    perc = PercView()
    lane_count = int(fp.get("lane_count") or 0)
    avail = int(fp.get("lane_avail") or 0)
    conf = float(fp.get("lane_conf") or 0.0)
    map_vr = float(fp.get("lane_vr_end_m") or 0.0)
    if map_vr > _VR_CAP:
        map_vr = _VR_CAP
    vr_end = map_vr

    left_c0 = float(fp.get("host_left_c0") or 1.75)
    right_c0 = float(fp.get("host_right_c0") or -1.75)
    host_c1 = float(fp.get("host_c1") or 0.0)
    host_c2 = float(fp.get("host_c2") or 0.0)
    left_c1 = float(fp.get("host_left_c1") or 0.0) or host_c1
    right_c1 = float(fp.get("host_right_c1") or 0.0) or host_c1
    left_c2 = float(fp.get("host_left_c2") or 0.0) or host_c2
    right_c2 = float(fp.get("host_right_c2") or 0.0) or host_c2
    left_type = int(fp.get("host_left_type") or 1) or 1
    right_type = int(fp.get("host_right_type") or 1) or 1
    width = float(fp.get("lane_width_m") or 3.5)

    if lane_count == 0:
        left_c0, right_c0 = 1.75, -1.75
        width = 3.5
        left_c1 = right_c1 = left_c2 = right_c2 = 0.0
        left_type = right_type = 1
        avail = 0
        conf = 0.0
        vr_end = 0.0
        map_vr = 0.0
    if width < 0.5:
        width = max(2.5, left_c0 - right_c0)

    objs_in = fp.get("obj") or []
    dyn_n = min(13, int(fp.get("dyn_n") or 0))
    for i, o in enumerate(objs_in[:dyn_n]):
        perc.objects.append(
            DynObj(
                obj_id=int(o.get("id") or (i + 1)),
                obj_class=int(o.get("cls") or 1),
                long_m=float(o.get("long_m") or 0.0),
                lat_m=float(o.get("lat_m") or 0.0),
                rel_v_mps=float(o.get("rel_v_mps") or 0.0),
                heading_rad=float(o.get("heading_rad") or 0.0),
                len_m=float(o.get("len_m") or 4.5),
                wid_m=float(o.get("wid_m") or 1.8),
                is_ped=int(o.get("is_ped") or 0),
                assign=int(o.get("assign") or 3),
            )
        )

    for i, o in enumerate(fp.get("stat") or []):
        perc.static.append(
            DynObj(
                obj_id=int(o.get("id") or (i + 1)),
                obj_class=int(o.get("cls") or 1),
                long_m=float(o.get("long_m") or 0.0),
                lat_m=float(o.get("lat_m") or 0.0),
                rel_v_mps=0.0,
                heading_rad=float(o.get("heading_rad") or 0.0),
                len_m=float(o.get("len_m") or 2.0),
                wid_m=float(o.get("wid_m") or 0.6),
                assign=int(o.get("assign") or 3),
            )
        )

    if avail == 0 or vr_end < 0.5 or conf < 0.1:
        avail = 0
        conf = min(conf, 0.05)
        vr_end = 0.0
        map_vr = 0.0
        left_c2 = right_c2 = 0.0

    perc.lane_width_m = width
    perc.lane_conf = conf
    perc.lane_count = lane_count
    if avail != 0:
        perc.host = [
            LaneLine(
                side=1,
                c0=left_c0,
                c1=left_c1,
                c2=left_c2,
                vr_end=vr_end,
                conf=conf,
                avail=avail,
                lanemark_type=left_type,
            ),
            LaneLine(
                side=2,
                c0=right_c0,
                c1=right_c1,
                c2=right_c2,
                vr_end=vr_end,
                conf=conf,
                avail=avail,
                lanemark_type=right_type,
            ),
        ]
        # Same as planning/driving HostLaneFromPerc (lite lane-keep).
        perc.lane_valid = True
        perc.c0 = 0.5 * (left_c0 + right_c0)
        perc.c1 = 0.5 * (left_c1 + right_c1)
        perc.c2 = 0.5 * (left_c2 + right_c2)
        perc.c3 = 0.0
        perc.e_y = perc.c0  # y_center(0)
        if width > 0.5:
            perc.lane_width_m = width
        else:
            perc.lane_width_m = max(2.5, abs(left_c0 - right_c0))
        perc.x_end = vr_end if vr_end > 0.5 else 60.0

    adj_n = int(fp.get("adj_n") or 0) if avail == 2 else 0
    adj_n = min(4, max(0, adj_n))
    for i in range(adj_n):
        side = int(fp["adj_side"][i])
        c0 = float(fp["adj_c0"][i])
        if not _keep_adj(side):
            continue
        perc.adj.append(
            LaneLine(
                side=side,
                c0=c0,
                c1=float(fp["adj_c1"][i]),
                c2=float(fp["adj_c2"][i]),
                vr_end=map_vr,
                conf=conf * 0.95,
                avail=avail,
                lanemark_type=int(fp["adj_type"][i]) or 2,
            )
        )

    for o in fp.get("tsr") or []:
        perc.tsr.append(
            TsrItem(
                name=int(o.get("name") or 0),
                long_m=float(o.get("long_m") or 0.0),
                lat_m=float(o.get("lat_m") or 0.0),
                relevancy=int(o.get("rel") or 0),
            )
        )
    perc.vd_count = int(fp.get("vd_count") or 0)
    perc.ped_count = int(fp.get("ped_count") or 0)
    perc.cipv_id = int(fp.get("cipv_id") or 0)

    lead_valid = bool(fp.get("lead_valid"))
    lead_d = float(fp.get("lead_distance_m") or 0.0)
    lead_lat = float(fp.get("lead_lat_m") or 0.0)
    # Contact (d≈0) is still a lead — classify as AEB, not empty-road cruise.
    if lead_valid and lead_d >= 0.0:
        perc.lead_valid = True
        perc.lead_distance_m = lead_d
        perc.lead_rel_speed_mps = float(fp.get("lead_rel_speed_mps") or 0.0)
        perc.lead_lat_m = lead_lat
        perc.lead_heading_rad = float(fp.get("lead_heading_rad") or 0.0)
    elif perc.objects:
        cipv = next((o for o in perc.objects if o.obj_id == perc.cipv_id), None)
        lead = cipv or perc.objects[0]
        if lead.long_m >= 0.0:
            perc.lead_valid = True
            perc.lead_distance_m = lead.long_m
            perc.lead_rel_speed_mps = lead.rel_v_mps
            perc.lead_lat_m = lead.lat_m
            perc.lead_heading_rad = lead.heading_rad
            if not perc.cipv_id:
                perc.cipv_id = lead.obj_id
    return perc


def build_view(
    *,
    state: Optional[dict[str, Any]],
    fake_perc: Optional[dict[str, Any]],
    source: str = "fake_perc",
) -> PlanningView:
    view = PlanningView(source=source)
    if state:
        view.stamp_ns = int(state.get("timestamp_ns") or 0)
        view.ego = EgoView(
            speed_mps=float(state.get("speed_mps") or 0.0),
            yaw_rate_degps=float(state.get("yaw_rate_degps") or 0.0),
            steer_angle_deg=float(state.get("steer_angle_deg") or 0.0),
            gear=int(state.get("gear") or 4),
        )
    if fake_perc and int(fake_perc.get("valid") or 0):
        view.seq = int(fake_perc.get("seq") or 0)
        if int(fake_perc.get("timestamp_ns") or 0):
            view.stamp_ns = int(fake_perc["timestamp_ns"])
        view.perc = _fcm_style_perc(fake_perc)
    return view


def result_to_cmd_blob(result: PlanningResult, *, speed_mps: float, seq: int) -> bytes:
    mode = CTRL_MODE_IDS.get(result.ctrl_mode, 0)
    return P.pack_cmd(
        seq=seq,
        timestamp_ns=result.stamp_ns,
        throttle=result.throttle,
        brake=result.brake,
        steer=result.steer,
        target_speed_mps=result.target_speed_mps,
        speed_mps=speed_mps,
        ctrl_mode=mode,
        lane_code=result.lane_code,
    )


def lane_code_from_path(ys: list[float]) -> int:
    if not ys:
        return 0
    y_end = float(ys[-1])
    if y_end > 0.4:
        return 1
    if y_end < -0.4:
        return 2
    return 0


def view_to_bev_out_dict(view: PlanningView) -> dict[str, Any]:
    """Gold-like Perception_MESSAGE_Out_St dict for LiveBevComposer._apply_perc_out."""
    perc = view.perc
    host_items = []
    for ln in perc.host:
        host_items.append(
            {
                "m_LH_Side": ln.side,
                "m_LH_Confidence": ln.conf,
                "m_LH_Availability_State": ln.avail,
                "m_LH_Lanemark_Type": ln.lanemark_type,
                "m_LH_First_VR_Start": ln.vr_start,
                "m_LH_First_VR_End": ln.vr_end,
                "m_LH_Line_First_C0": ln.c0,
                "m_LH_Line_First_C1": ln.c1,
                "m_LH_Line_First_C2": ln.c2,
                "m_LH_Line_First_C3": ln.c3,
            }
        )
    adj_items = []
    for ln in perc.adj:
        adj_items.append(
            {
                "m_LA_Line_Side": ln.side,
                "m_LA_Confidence": ln.conf,
                "m_LA_Availability_State": ln.avail,
                "m_LA_Lanemark_Type": ln.lanemark_type,
                "m_LA_View_Range_Start": ln.vr_start,
                "m_LA_View_Range_End": ln.vr_end,
                "m_LA_Line_C0": ln.c0,
                "m_LA_Line_C1": ln.c1,
                "m_LA_Line_C2": ln.c2,
                "m_LA_Line_C3": ln.c3,
            }
        )
    obj_items = []
    for o in perc.objects:
        obj_items.append(
            {
                "m_OBJ_ID": o.obj_id,
                "m_OBJ_Object_Class": o.obj_class,
                "m_OBJ_Long_Distance": o.long_m,
                "m_OBJ_Lat_Distance": o.lat_m,
                "m_OBJ_Relative_Long_Velocity": o.rel_v_mps,
                "m_OBJ_Heading": o.heading_rad,
                "m_OBJ_Length": o.len_m,
                "m_OBJ_Width": o.wid_m,
            }
        )
    return {
        "Perception_LH_Out": {
            "m_hostline_num": len(host_items),
            "m_LH_Estimated_Width": perc.lane_width_m,
            "m_hostline": host_items,
        },
        "Perception_LA_Out": {
            "m_adj_line_num": len(adj_items),
            "m_adj_line": adj_items,
        },
        "Perception_DYN_OBJ_Out": {
            "m_OBJ_VD_Count": perc.vd_count or len(obj_items),
            "m_OBJ_Ped_Count": perc.ped_count,
            "m_OBJ_VD_CIPV_ID": perc.cipv_id,
            "m_Obj_item": obj_items,
        },
    }


def view_to_ego_dict(view: PlanningView) -> dict[str, Any]:
    return {
        "timestamp_ns": view.stamp_ns,
        "speed_mps": view.ego.speed_mps,
        "yaw_rate_degps": view.ego.yaw_rate_degps,
        "steer_angle_deg": view.ego.steer_angle_deg,
        "gear": view.ego.gear,
    }


def result_to_traj_dict(result: PlanningResult) -> dict[str, Any]:
    return {
        "timestamp_ns": result.stamp_ns,
        "points_x_m": list(result.points_x_m),
        "points_y_m": list(result.points_y_m),
        "points_v_mps": list(result.points_v_mps),
        "throttle": result.throttle,
        "brake": result.brake,
        "steer": result.steer,
        "target_speed_mps": result.target_speed_mps,
        "horizon_m": float(result.horizon_m),
        "D_see_m": float(result.D_see_m),
        "T_plan_s": float(result.T_plan_s),
        "allow_lc": int(result.allow_lc),
        "ctrl_mode": CTRL_MODE_IDS.get(result.ctrl_mode, 0),
    }
