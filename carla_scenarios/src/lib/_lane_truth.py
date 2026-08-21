"""CARLA → ego-frame lane topology for carla_truth (no Giraffe imports).

CARLA/Unreal: X forward, Y right+. Gold / this module: x forward, y left+.
lane_count: same-direction countable Driving lanes (Shoulder 等不计).
"""

from __future__ import annotations

import math
from typing import Any


def _carla():
    import carla  # type: ignore

    return carla


def _is_countable_lane(wp: Any) -> bool:
    """Driving only; Shoulder/Parking/Sidewalk/… 不算车道."""
    if wp is None:
        return False
    try:
        carla = _carla()
        lt = wp.lane_type
        bad = (
            int(carla.LaneType.Shoulder)
            | int(carla.LaneType.Parking)
            | int(carla.LaneType.Sidewalk)
            | int(carla.LaneType.Border)
            | int(carla.LaneType.Median)
            | int(carla.LaneType.Biking)
            | int(carla.LaneType.Stop)
            | int(carla.LaneType.Restricted)
        )
        if int(lt) & bad:
            return False
        return (int(lt) & int(carla.LaneType.Driving)) != 0 or lt == carla.LaneType.Driving
    except Exception:  # noqa: BLE001
        return True


def _same_dir(a: Any, b: Any) -> bool:
    try:
        return int(a.lane_id) * int(b.lane_id) > 0
    except Exception:  # noqa: BLE001
        return False


def _ego_yaw_rad(ego: Any) -> float:
    return math.radians(float(ego.get_transform().rotation.yaw))


def _wrap_pi(a: float) -> float:
    while a > math.pi:
        a -= 2.0 * math.pi
    while a < -math.pi:
        a += 2.0 * math.pi
    return a


def world_to_ego_xy(ego: Any, wx: float, wy: float) -> tuple[float, float]:
    """World XY → ego frame (x forward, y left+).

    CARLA/Unreal body: X forward, Y right+. Convert so gold y is left+:
      x =  cosθ·dx + sinθ·dy
      y_left = sinθ·dx - cosθ·dy   (= −y_ue_right)
    """
    et = ego.get_transform()
    el = et.location
    yaw = math.radians(float(et.rotation.yaw))
    dx = float(wx) - float(el.x)
    dy = float(wy) - float(el.y)
    c, s = math.cos(yaw), math.sin(yaw)
    xf = c * dx + s * dy
    y_ue_right = -s * dx + c * dy
    y_left = -y_ue_right
    return xf, y_left


def _shoulder_lane_ids(world: Any, ref_wp: Any) -> set[int]:
    """lane_id of Shoulder (etc.) on the same road — never countable."""
    out: set[int] = set()
    if world is None or ref_wp is None:
        return out
    try:
        carla = _carla()
        loc = ref_wp.transform.location
        road_id = int(ref_wp.road_id)
        for ltype in (
            carla.LaneType.Shoulder,
            carla.LaneType.Parking,
            carla.LaneType.Border,
            carla.LaneType.Sidewalk,
        ):
            try:
                swp = world.get_map().get_waypoint(
                    loc, project_to_road=True, lane_type=ltype
                )
            except Exception:  # noqa: BLE001
                continue
            if swp is None:
                continue
            try:
                if int(swp.road_id) != road_id:
                    continue
                if not _same_dir(ref_wp, swp):
                    continue
                out.add(int(swp.lane_id))
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        return out
    return out


def _lane_chain_from_left(wp: Any, *, exclude_ids: set[int] | None = None) -> list[Any]:
    """Same-direction countable lanes, leftmost → rightmost."""
    if not _is_countable_lane(wp):
        return []
    exclude_ids = exclude_ids or set()

    def _ok(w: Any) -> bool:
        if not _is_countable_lane(w):
            return False
        try:
            if int(w.lane_id) in exclude_ids:
                return False
        except Exception:  # noqa: BLE001
            pass
        return True

    cur = wp
    guard = 0
    while guard < 16:
        left = cur.get_left_lane()
        if left is None or not _same_dir(cur, left):
            break
        if not _ok(left):
            # Shoulder / excluded on the left — stop (do not enter).
            break
        cur = left
        guard += 1
    out: list[Any] = []
    guard = 0
    while cur is not None and guard < 16:
        if _ok(cur):
            out.append(cur)
        right = cur.get_right_lane()
        if right is None or not _same_dir(cur, right):
            break
        if not _ok(right):
            break
        cur = right
        guard += 1
    return out


def _road_c1(ego: Any, wp: Any) -> float:
    """Lane-center slope dy/dx in ego frame from road vs ego yaw."""
    try:
        lane_yaw = math.radians(float(wp.transform.rotation.yaw))
    except Exception:  # noqa: BLE001
        return 0.0
    psi = _wrap_pi(lane_yaw - _ego_yaw_rad(ego))
    psi = max(-1.2, min(1.2, psi))
    return math.tan(psi)


def _fit_c0_c1_c2(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """Least-squares y ≈ c0 + c1 x + c2 x²."""
    n = len(xs)
    if n < 1:
        return 0.0, 0.0, 0.0
    if n == 1:
        return float(ys[0]), 0.0, 0.0
    if n == 2:
        dx = xs[1] - xs[0]
        c1 = (ys[1] - ys[0]) / dx if abs(dx) > 1e-3 else 0.0
        return float(ys[0] - c1 * xs[0]), float(c1), 0.0
    ata = [[0.0] * 3 for _ in range(3)]
    aty = [0.0, 0.0, 0.0]
    for x, y in zip(xs, ys):
        row = (1.0, x, x * x)
        for i in range(3):
            aty[i] += row[i] * y
            for j in range(3):
                ata[i][j] += row[i] * row[j]
    m = [ata[i][:] + [aty[i]] for i in range(3)]
    try:
        for col in range(3):
            piv = max(range(col, 3), key=lambda r: abs(m[r][col]))
            if abs(m[piv][col]) < 1e-12:
                raise ZeroDivisionError
            m[col], m[piv] = m[piv], m[col]
            div = m[col][col]
            for j in range(col, 4):
                m[col][j] /= div
            for r in range(3):
                if r == col:
                    continue
                f = m[r][col]
                for j in range(col, 4):
                    m[r][j] -= f * m[col][j]
        return float(m[0][3]), float(m[1][3]), float(m[2][3])
    except Exception:  # noqa: BLE001
        c1 = (ys[-1] - ys[0]) / max(1e-3, xs[-1] - xs[0])
        return float(ys[0]), float(c1), 0.0


def _sample_edge_poly(
    ego: Any, wp: Any, *, side: str, half_w: float, horizon_m: float = 80.0
) -> tuple[float, float, float]:
    """Sample lane edge ahead in ego frame → (c0, c1, c2). y left+.

    CARLA/Unreal left at yaw θ: (sin θ, −cos θ); right = opposite.
    """
    xs: list[float] = []
    ys: list[float] = []
    cur = wp
    dist = 0.0
    sign = 1.0 if side == "left" else -1.0
    for _ in range(16):
        try:
            loc = cur.transform.location
            yaw = math.radians(float(cur.transform.rotation.yaw))
            # UE left = (sin, -cos)
            lx = float(loc.x) + sign * half_w * math.sin(yaw)
            ly = float(loc.y) + sign * half_w * (-math.cos(yaw))
            xe, ye = world_to_ego_xy(ego, lx, ly)
            if xe >= -2.0:
                xs.append(xe)
                ys.append(ye)
        except Exception:  # noqa: BLE001
            break
        if dist >= horizon_m:
            break
        try:
            nxt = cur.next(5.0)
            if not nxt:
                break
            cur = nxt[0]
            dist += 5.0
        except Exception:  # noqa: BLE001
            break
    if not xs:
        c1 = _road_c1(ego, wp)
        return sign * half_w, c1, 0.0
    return _fit_c0_c1_c2(xs, ys)


def _dedup_edges(
    raw: list[dict[str, Any]], *, merge_m: float = 0.35
) -> list[dict[str, Any]]:
    """Keep unique laterals (by c0), left (high y) → right."""
    if not raw:
        return []
    ordered = sorted(raw, key=lambda e: -float(e["c0"]))
    out: list[dict[str, Any]] = [ordered[0]]
    for e in ordered[1:]:
        if abs(float(e["c0"]) - float(out[-1]["c0"])) < merge_m:
            prev = out[-1]
            out[-1] = {
                "c0": 0.5 * (float(prev["c0"]) + float(e["c0"])),
                "c1": 0.5 * (float(prev["c1"]) + float(e["c1"])),
                "c2": 0.5 * (float(prev["c2"]) + float(e["c2"])),
                "lane_i": prev.get("lane_i", e.get("lane_i")),
                "kind": "shared",
            }
        else:
            out.append(dict(e))
    return out


def _side_code_for_edge(
    c0: float, *, host_left: float, host_right: float, ego_idx: int, n_lanes: int
) -> int:
    """Map corridor edge to gold LA_Line_Side relative to host."""
    if c0 > host_left + 0.2:
        if ego_idx >= 2 and c0 > host_left + 3.0:
            return 6
        return 1
    if c0 < host_right - 0.2:
        if ego_idx + 2 < n_lanes and c0 < host_right - 3.0:
            return 5
        return 4
    if abs(c0 - host_left) <= abs(c0 - host_right):
        return 2
    return 3


def measure_lane_topology(ego: Any, world: Any) -> dict[str, Any]:
    """Return truth fields for lanes; empty-ish dict if map lookup fails."""
    empty: dict[str, Any] = {
        "lane_count": 0,
        "ego_lane_index_from_left": 0,
        "lane_width_m": 3.5,
        "host_left_c0": 1.75,
        "host_right_c0": -1.75,
        "host_c1": 0.0,
        "host_c2": 0.0,
        "adj_n": 0,
        "lane_avail": 0,
        "lane_conf": 0.0,
        "lane_vr_end_m": 0.0,
        "lane_quality_reason": "no_map",
    }
    try:
        carla = _carla()
    except ImportError:
        return empty

    try:
        el = ego.get_location()
        wp = world.get_map().get_waypoint(
            el, project_to_road=True, lane_type=carla.LaneType.Driving
        )
    except Exception:  # noqa: BLE001
        return empty
    if wp is None:
        return empty

    # If project landed on a non-countable / excluded id, step to neighbor Driving.
    exclude_ids = _shoulder_lane_ids(world, wp)
    if not _is_countable_lane(wp) or (
        exclude_ids and int(getattr(wp, "lane_id", -1)) in exclude_ids
    ):
        for step in (wp.get_right_lane, wp.get_left_lane):
            try:
                alt = step()
            except Exception:  # noqa: BLE001
                alt = None
            if (
                alt is not None
                and _same_dir(wp, alt)
                and _is_countable_lane(alt)
                and int(alt.lane_id) not in exclude_ids
            ):
                wp = alt
                break

    chain = _lane_chain_from_left(wp, exclude_ids=exclude_ids)
    if not chain:
        return empty

    ego_idx = 0
    try:
        eid = int(wp.lane_id)
        for i, w in enumerate(chain):
            if int(w.lane_id) == eid:
                ego_idx = i
                break
    except Exception:  # noqa: BLE001
        ego_idx = 0

    ego_wp = chain[ego_idx]
    try:
        width = float(ego_wp.lane_width) or 3.5
    except Exception:  # noqa: BLE001
        width = 3.5
    width = max(2.5, min(width, 5.0))

    raw_edges: list[dict[str, Any]] = []
    lane_lr: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for i, awp in enumerate(chain):
        try:
            aw = float(awp.lane_width) or width
        except Exception:  # noqa: BLE001
            aw = width
        ah = 0.5 * max(2.5, min(aw, 5.0))
        lc0, lc1, lc2 = _sample_edge_poly(ego, awp, side="left", half_w=ah)
        rc0, rc1, rc2 = _sample_edge_poly(ego, awp, side="right", half_w=ah)
        left_e = {"c0": lc0, "c1": lc1, "c2": lc2, "lane_i": i, "kind": "left"}
        right_e = {"c0": rc0, "c1": rc1, "c2": rc2, "lane_i": i, "kind": "right"}
        lane_lr.append((left_e, right_e))
        raw_edges.append(left_e)
        raw_edges.append(right_e)

    corridor = _dedup_edges(raw_edges, merge_m=0.35)
    if len(corridor) < 2:
        return empty

    host_l = dict(lane_lr[ego_idx][0])
    host_r = dict(lane_lr[ego_idx][1])

    def _nearest(c0: float) -> dict[str, Any]:
        return min(corridor, key=lambda e: abs(float(e["c0"]) - c0))

    host_l = dict(_nearest(float(host_l["c0"])))
    host_r = dict(_nearest(float(host_r["c0"])))

    hl_c0 = float(host_l["c0"])
    hr_c0 = float(host_r["c0"])
    hl_c1 = float(host_l["c1"])
    hr_c1 = float(host_r["c1"])
    hl_c2 = float(host_l["c2"])
    hr_c2 = float(host_r["c2"])
    c1 = 0.5 * (hl_c1 + hr_c1)
    c2 = 0.5 * (hl_c2 + hr_c2)

    adj: list[dict[str, Any]] = []
    for e in corridor:
        c0 = float(e["c0"])
        if abs(c0 - hl_c0) < 0.3 or abs(c0 - hr_c0) < 0.3:
            continue
        side = _side_code_for_edge(
            c0, host_left=hl_c0, host_right=hr_c0, ego_idx=ego_idx, n_lanes=len(chain)
        )
        adj.append(
            {
                "side": side,
                "c0": c0,
                "c1": float(e["c1"]),
                "c2": float(e["c2"]),
            }
        )
        if len(adj) >= 4:
            break

    all_c0 = [hl_c0, hr_c0] + [float(a["c0"]) for a in adj]
    y_lo, y_hi = min(all_c0), max(all_c0)

    def mark_type(c0: float) -> int:
        if abs(c0 - y_hi) < 0.35 or abs(c0 - y_lo) < 0.35:
            return 1
        return 2

    # Geometry gate for ego-frame y=f(x) (blob / 一坨): quality → FCM Availability/Conf/VR.
    q = assess_lane_poly_quality(
        host_left_c0=hl_c0,
        host_right_c0=hr_c0,
        host_c1=c1,
        host_c2=c2,
        lane_width_m=width,
    )
    # Invalid ego-frame poly only when avail==0: drop adj + kill C2 in truth.
    # Degraded (avail==1, e.g. lat offset) keeps host coeffs + adj in truth;
    # FCM may still omit adj when avail!=2.
    if q["lane_avail"] == 0:
        adj = []
        c2 = 0.0
        hl_c2 = 0.0
        hr_c2 = 0.0

    out: dict[str, Any] = {
        "lane_count": len(chain),
        "ego_lane_index_from_left": ego_idx,
        "lane_width_m": width,
        "host_left_c0": hl_c0,
        "host_right_c0": hr_c0,
        "host_c1": c1,
        "host_c2": c2,
        "host_left_c1": hl_c1,
        "host_right_c1": hr_c1,
        "host_left_c2": hl_c2,
        "host_right_c2": hr_c2,
        "host_left_type": mark_type(hl_c0),
        "host_right_type": mark_type(hr_c0),
        "adj_n": len(adj),
        "corridor_edge_n": len(corridor),
        "lane_avail": int(q["lane_avail"]),
        "lane_conf": float(q["lane_conf"]),
        "lane_vr_end_m": float(q["lane_vr_end_m"]),
        "lane_quality_reason": str(q["reason"]),
    }
    for i, a in enumerate(adj):
        out[f"adj{i}_side"] = int(a["side"])
        out[f"adj{i}_c0"] = float(a["c0"])
        out[f"adj{i}_c1"] = float(a["c1"])
        out[f"adj{i}_c2"] = float(a["c2"])
        out[f"adj{i}_type"] = mark_type(float(a["c0"]))
    return out


def assess_lane_poly_quality(
    *,
    host_left_c0: float,
    host_right_c0: float,
    host_c1: float,
    host_c2: float,
    lane_width_m: float,
    vr_full_m: float = 130.0,
) -> dict[str, Any]:
    """Decide Availability / Confidence / VR_End for ego-frame lane polys.

    Gold-like: 0=NOT_AVAILABLE, 1=PREDICATED(degraded), 2=DETECTED(ok).
    Hard NA only for unusable y=f(x) (extreme yaw / collapsed width / absurd offset).
    Large lateral offset alone → degrade + short VR (still drawable), not blackout.
    """
    width = max(2.0, float(lane_width_m) if lane_width_m > 0.5 else 3.5)
    mid = 0.5 * (float(host_left_c0) + float(host_right_c0))
    half = 0.5 * abs(float(host_left_c0) - float(host_right_c0))
    if half < 0.5:
        half = 0.5 * width
    psi = abs(math.atan(float(host_c1)))
    abs_c2 = abs(float(host_c2))
    lat_off = abs(mid)

    # Hard fail: model is not usable even near-field
    if psi > math.radians(40.0):
        return {
            "lane_avail": 0,
            "lane_conf": 0.05,
            "lane_vr_end_m": 0.0,
            "reason": "poly_invalid_yaw",
        }
    if half > 0.1 and abs(float(host_left_c0) - float(host_right_c0)) < 0.4:
        return {
            "lane_avail": 0,
            "lane_conf": 0.05,
            "lane_vr_end_m": 0.0,
            "reason": "poly_collapsed_width",
        }
    # Absurd offset (corridor unrelated to ego) — still NA
    if lat_off > 2.5 * width and psi > math.radians(25.0):
        return {
            "lane_avail": 0,
            "lane_conf": 0.05,
            "lane_vr_end_m": 0.0,
            "reason": "poly_invalid_yaw_or_lat",
        }

    vr = float(vr_full_m)
    conf = 0.95
    avail = 2
    reason = "ok"

    # Soft: large lateral alone → keep lines, shorten VR (do not blackout)
    if lat_off > 1.15 * width:
        avail = 1
        conf = 0.35
        vr = min(vr, 25.0)
        reason = "poly_lat_offset"
    elif psi > math.radians(25.0) or lat_off > 0.55 * width or abs_c2 > 0.02:
        avail = 1
        conf = 0.45
        vr = min(vr, 35.0)
        reason = "poly_degraded"
    if psi > math.radians(32.0) or abs_c2 > 0.035:
        avail = 1 if avail == 2 else avail
        conf = min(conf, 0.30)
        vr = min(vr, 20.0)
        if reason == "ok":
            reason = "poly_short_vr"
    return {
        "lane_avail": avail,
        "lane_conf": conf,
        "lane_vr_end_m": max(0.0, vr),
        "reason": reason,
    }


def lead_ego_frame(ego: Any, lead: Any) -> tuple[float, float, int, float]:
    """(long_m, lat_m left+, lane_assignment, heading_rad vs ego +x)."""
    if lead is None:
        return 0.0, 0.0, 0, 0.0
    ll = lead.get_location()
    x, y = world_to_ego_xy(ego, float(ll.x), float(ll.y))
    assign = 3  # HOST
    if y > 1.5:
        assign = 2  # LEFT
    elif y < -1.5:
        assign = 4  # RIGHT
    if abs(y) > 4.5:
        assign = 1 if y > 0 else 5
    try:
        lead_yaw = math.radians(float(lead.get_transform().rotation.yaw))
        heading = _wrap_pi(lead_yaw - _ego_yaw_rad(ego))
    except Exception:  # noqa: BLE001
        heading = 0.0
    return max(0.0, x), y, assign, heading
