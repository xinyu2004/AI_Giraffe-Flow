"""Pick transforms only — no actors, no speed, no keep_ego."""

from __future__ import annotations

from typing import Any, Optional, Tuple


def _waypoint_ahead(wp: Any, distance_m: float) -> Optional[Any]:
    cur = wp
    left = float(distance_m)
    step = 2.0
    while left > 0.1:
        d = min(step, left)
        nxt = cur.next(d)
        if not nxt:
            return None
        cur = nxt[0]
        left -= d
    return cur


def _yaw_delta_deg(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return d if d <= 180.0 else 360.0 - d


def _straightness_score(wp: Any, length_m: float, sample_step: float = 5.0) -> Optional[float]:
    yaw0 = wp.transform.rotation.yaw
    max_delta = 0.0
    cur = wp
    walked = 0.0
    while walked < length_m:
        nxt = cur.next(sample_step)
        if not nxt:
            return None
        cur = nxt[0]
        if cur.is_junction:
            return None
        walked += sample_step
        max_delta = max(max_delta, _yaw_delta_deg(yaw0, cur.transform.rotation.yaw))
    if max_delta > 8.0:
        return None
    return 100.0 - max_delta


def pick_follow_transforms(
    world: Any,
    *,
    lead_gap_m: float,
    clear_ahead_m: float = 50.0,
    require_straight: bool = True,
) -> Tuple[Any, Any]:
    """Pick ego + lead on a driving lane. ACC/AEB: require_straight=True."""
    import carla  # type: ignore

    m = world.get_map()
    spawns = m.get_spawn_points()
    if not spawns:
        raise RuntimeError("no CARLA spawn points")

    need = lead_gap_m + clear_ahead_m
    best: Optional[Tuple[Any, Any, float]] = None

    for sp in spawns:
        wp = m.get_waypoint(
            sp.location,
            project_to_road=True,
            lane_type=carla.LaneType.Driving,
        )
        if wp is None or wp.is_junction:
            continue
        lead_wp = _waypoint_ahead(wp, lead_gap_m)
        if lead_wp is None or lead_wp.is_junction:
            continue
        end_wp = _waypoint_ahead(lead_wp, clear_ahead_m)
        if end_wp is None:
            continue

        if require_straight:
            st = _straightness_score(wp, need)
            if st is None:
                continue
            score = st + need * 0.01
        else:
            score = need

        ego_tf = wp.transform
        ego_tf.location.z += 0.3
        lead_tf = lead_wp.transform
        lead_tf.location.z += 0.3
        if best is None or score > best[2]:
            best = (ego_tf, lead_tf, score)

    if best is None and require_straight:
        return pick_follow_transforms(
            world,
            lead_gap_m=lead_gap_m,
            clear_ahead_m=clear_ahead_m,
            require_straight=False,
        )

    if best is None:
        ego_tf = spawns[0]
        fwd = ego_tf.get_forward_vector()
        lead_tf = carla.Transform(
            carla.Location(
                x=ego_tf.location.x + fwd.x * lead_gap_m,
                y=ego_tf.location.y + fwd.y * lead_gap_m,
                z=ego_tf.location.z + 0.5,
            ),
            ego_tf.rotation,
        )
        return ego_tf, lead_tf

    return best[0], best[1]


def _lane_side(wp: Any, side: str) -> Optional[Any]:
    if side == "left":
        return wp.get_left_lane()
    if side == "right":
        return wp.get_right_lane()
    return None


def pick_cut_in_transforms(
    world: Any,
    *,
    lead_gap_m: float = 28.0,
    side: str = "left",
) -> Tuple[Any, Any, Any]:
    """Ego on lane; lead ahead on adjacent lane. Returns (ego_tf, lead_tf, ego_wp)."""
    import carla  # type: ignore

    m = world.get_map()
    for sp in m.get_spawn_points():
        wp = m.get_waypoint(
            sp.location, project_to_road=True, lane_type=carla.LaneType.Driving
        )
        if wp is None or wp.is_junction:
            continue
        adj = _lane_side(wp, side)
        if adj is None or adj.lane_type != carla.LaneType.Driving:
            continue
        lead_wp = _waypoint_ahead(adj, lead_gap_m)
        if lead_wp is None:
            continue
        ego_tf = wp.transform
        ego_tf.location.z += 0.3
        lead_tf = lead_wp.transform
        lead_tf.location.z += 0.3
        return ego_tf, lead_tf, wp

    ego_tf, lead_tf = pick_follow_transforms(world, lead_gap_m=lead_gap_m)
    return ego_tf, lead_tf, None


def pick_curve_transform(
    world: Any,
    *,
    look_ahead_m: float = 40.0,
    min_yaw_delta_deg: float = 12.0,
) -> Any:
    """Prefer a driving spawn that bends ahead (LKA / curve cases)."""
    import carla  # type: ignore

    m = world.get_map()
    best: Optional[Tuple[Any, float]] = None
    for sp in m.get_spawn_points():
        wp = m.get_waypoint(
            sp.location, project_to_road=True, lane_type=carla.LaneType.Driving
        )
        if wp is None or wp.is_junction:
            continue
        yaw0 = wp.transform.rotation.yaw
        end = _waypoint_ahead(wp, look_ahead_m)
        if end is None:
            continue
        delta = _yaw_delta_deg(yaw0, end.transform.rotation.yaw)
        if delta < min_yaw_delta_deg:
            continue
        score = delta
        if best is None or score > best[1]:
            tf = wp.transform
            tf.location.z += 0.3
            best = (tf, score)
    if best is not None:
        return best[0]
    spawns = m.get_spawn_points()
    if not spawns:
        raise RuntimeError("no CARLA spawn points")
    tf = spawns[0]
    tf.location.z += 0.3
    return tf


def offset_transform(tf: Any, *, forward_m: float = 0.0, right_m: float = 0.0) -> Any:
    import carla  # type: ignore
    import math

    yaw = math.radians(tf.rotation.yaw)
    loc = carla.Location(
        x=tf.location.x + math.cos(yaw) * forward_m + math.cos(yaw + math.pi / 2) * right_m,
        y=tf.location.y + math.sin(yaw) * forward_m + math.sin(yaw + math.pi / 2) * right_m,
        z=tf.location.z,
    )
    return carla.Transform(loc, tf.rotation)
