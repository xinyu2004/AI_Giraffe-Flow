"""Pick transforms only — no actors, no speed, no keep_ego."""

from __future__ import annotations

from typing import Any, Optional, Tuple

# Sit on the pavement, not in the air. Physics-on from +0.3…0.5 m looks like a drop.
_GROUND_Z_CLEAR_M = 0.08


def _same_dir_lane(a: Any, b: Any) -> bool:
    try:
        return int(a.lane_id) * int(b.lane_id) > 0
    except Exception:  # noqa: BLE001
        return False


def _lane_is_driving(wp: Any) -> bool:
    if wp is None:
        return False
    try:
        import carla  # type: ignore

        lt = int(wp.lane_type)
        bad = (
            int(carla.LaneType.Shoulder)
            | int(carla.LaneType.Parking)
            | int(carla.LaneType.Sidewalk)
            | int(carla.LaneType.Border)
            | int(carla.LaneType.Median)
        )
        if lt & bad:
            return False
        return (lt & int(carla.LaneType.Driving)) != 0
    except Exception:  # noqa: BLE001
        return True


def prefer_center_lane(wp: Any) -> Any:
    """Walk to a non-leftmost same-direction Driving lane when several exist.

    n==1 → that lane; n==2 → the right of the pair; n>=3 → near (n-1)//2.
    """
    if wp is None or not _lane_is_driving(wp):
        return wp
    cur = wp
    guard = 0
    while guard < 16:
        left = cur.get_left_lane()
        if left is None or not _same_dir_lane(cur, left) or not _lane_is_driving(left):
            break
        cur = left
        guard += 1
    chain: list[Any] = []
    guard = 0
    while cur is not None and guard < 16:
        if _lane_is_driving(cur):
            chain.append(cur)
        right = cur.get_right_lane()
        if right is None or not _same_dir_lane(cur, right) or not _lane_is_driving(right):
            break
        cur = right
        guard += 1
    if len(chain) <= 1:
        return wp
    idx = (len(chain) - 1) // 2
    if idx == 0:
        idx = 1
    return chain[idx]


def tf_on_lane(wp: Any) -> Any:
    """Waypoint pose, yaw = road, z = pavement + small clearance."""
    import carla  # type: ignore

    loc = wp.transform.location
    yaw = float(wp.transform.rotation.yaw)
    return carla.Transform(
        carla.Location(
            x=float(loc.x),
            y=float(loc.y),
            z=float(loc.z) + _GROUND_Z_CLEAR_M,
        ),
        carla.Rotation(pitch=0.0, yaw=yaw, roll=0.0),
    )


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
        wp = prefer_center_lane(wp)
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
            # Prefer wider lanes / more center-like corridor (less curb/barrier risk).
            score = st + need * 0.01 + float(getattr(wp, "lane_width", 3.5)) * 3.0
        else:
            score = need + float(getattr(wp, "lane_width", 3.5))

        ego_tf = tf_on_lane(wp)
        lead_tf = tf_on_lane(lead_wp)
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
                z=float(ego_tf.location.z),
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
        wp = prefer_center_lane(wp)
        if wp is None or wp.is_junction:
            continue
        adj = _lane_side(wp, side)
        if adj is None or adj.lane_type != carla.LaneType.Driving:
            continue
        lead_wp = _waypoint_ahead(adj, lead_gap_m)
        if lead_wp is None:
            continue
        return tf_on_lane(wp), tf_on_lane(lead_wp), wp

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
        wp = prefer_center_lane(wp)
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
            best = (tf_on_lane(wp), score)
    if best is not None:
        return best[0]
    spawns = m.get_spawn_points()
    if not spawns:
        raise RuntimeError("no CARLA spawn points")
    wp0 = m.get_waypoint(
        spawns[0].location, project_to_road=True, lane_type=carla.LaneType.Driving
    )
    if wp0 is not None:
        return tf_on_lane(prefer_center_lane(wp0) or wp0)
    tf = spawns[0]
    tf.location.z = float(tf.location.z) + _GROUND_Z_CLEAR_M
    tf.rotation.pitch = 0.0
    tf.rotation.roll = 0.0
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


def pick_lead_ahead_of(
    world: Any,
    ego_tf: Any,
    *,
    lead_gap_m: float,
) -> Any:
    """Lead pose ahead of current ego along the driving lane (batch continue)."""
    import carla  # type: ignore

    m = world.get_map()
    wp = m.get_waypoint(
        ego_tf.location,
        project_to_road=True,
        lane_type=carla.LaneType.Driving,
    )
    if wp is None:
        return offset_transform(ego_tf, forward_m=float(lead_gap_m))
    lead_wp = _waypoint_ahead(wp, float(lead_gap_m))
    if lead_wp is None:
        return offset_transform(ego_tf, forward_m=float(lead_gap_m))
    return tf_on_lane(lead_wp)
