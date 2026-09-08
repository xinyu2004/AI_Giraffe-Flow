"""Lane split / merge roadway stress layouts (best-effort on Town maps)."""

from __future__ import annotations

from typing import Any, Optional, Tuple

from spawn.pick import pick_follow_transforms
from spawn.place import spawn_ego_only
from _verdict import CmdProbe, release_ego


def _pick_multi_lane(world: Any, *, prefer_more: bool) -> Any:
    import carla  # type: ignore

    m = world.get_map()
    best = None
    best_n = -1 if prefer_more else 99
    for sp in m.get_spawn_points():
        wp = m.get_waypoint(
            sp.location, project_to_road=True, lane_type=carla.LaneType.Driving
        )
        if wp is None:
            continue
        n = 1
        cur = wp
        for _ in range(4):
            left = cur.get_left_lane()
            if left is None or left.lane_type != carla.LaneType.Driving:
                break
            n += 1
            cur = left
        cur = wp
        for _ in range(4):
            right = cur.get_right_lane()
            if right is None or right.lane_type != carla.LaneType.Driving:
                break
            n += 1
            cur = right
        if prefer_more:
            if n > best_n:
                best_n = n
                tf = wp.transform
                tf.location.z += 0.3
                best = tf
        else:
            if 1 <= n < best_n:
                best_n = n
                tf = wp.transform
                tf.location.z += 0.3
                best = tf
    if best is not None:
        return best
    ego_tf, _ = pick_follow_transforms(world, lead_gap_m=20.0)
    return ego_tf


def layout_lane_split(
    session: Any,
    *,
    keep_ego: bool = False,
    ego_mps: float = 10.0,
) -> Tuple[Any, Optional[Any], dict[str, Any]]:
    world = session.world
    carla_mod = session.carla
    tf = _pick_multi_lane(world, prefer_more=True)
    ego = spawn_ego_only(world, ego_tf=tf, keep_ego=keep_ego)
    release_ego(carla_mod, ego, session=session)
    mps = float(ego_mps)
    print(f"[layout] LANE_SPLIT ego={ego.id} (Giraffe drives)", flush=True)
    return ego, None, {
        "layout": "env_lane_split",
        "ego_mps": mps,
        "const_vel": False,
        "ic": "giraffe_only",
    }


def layout_lane_merge(
    session: Any,
    *,
    keep_ego: bool = False,
    ego_mps: float = 10.0,
) -> Tuple[Any, Optional[Any], dict[str, Any]]:
    world = session.world
    carla_mod = session.carla
    tf = _pick_multi_lane(world, prefer_more=False)
    ego = spawn_ego_only(world, ego_tf=tf, keep_ego=keep_ego)
    release_ego(carla_mod, ego, session=session)
    mps = float(ego_mps)
    print(f"[layout] LANE_MERGE ego={ego.id} (Giraffe drives)", flush=True)
    return ego, None, {
        "layout": "env_lane_merge",
        "ego_mps": mps,
        "const_vel": False,
        "ic": "giraffe_only",
    }


def tick_road_handoff(
    elapsed: float,
    ego: Any,
    _t: Optional[Any],
    meta: dict[str, Any],
    cmd: CmdProbe,
) -> None:
    del ego
    if meta.get("handed_off") or not cmd.seen_control:
        return
    meta["handed_off"] = True
    print(f"[layout] roadway Giraffe cmd at t={elapsed:.2f}s", flush=True)
