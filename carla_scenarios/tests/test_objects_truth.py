"""Unit tests for collect_dyn_objects (no CARLA)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_LIB = Path(__file__).resolve().parents[1] / "src" / "lib"
sys.path.insert(0, str(_LIB))

from _objects_truth import (  # noqa: E402
    collect_dyn_objects,
    drop_host_behind_occupy,
    optic_in_wedge,
    reset_dyn_object_cache,
)


@pytest.fixture(autouse=True)
def _reset_dyn_cache() -> None:
    reset_dyn_object_cache()
    yield
    reset_dyn_object_cache()


class _Loc:
    def __init__(self, x: float, y: float, z: float = 0.0) -> None:
        self.x, self.y, self.z = x, y, z


class _Rot:
    def __init__(self, yaw: float = 0.0) -> None:
        self.yaw = yaw


class _Tf:
    def __init__(self, x: float, y: float, yaw: float = 0.0) -> None:
        self.location = _Loc(x, y)
        self.rotation = _Rot(yaw)


class _Vel:
    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> None:
        self.x, self.y, self.z = x, y, z


class _Actor:
    def __init__(
        self,
        aid: int,
        type_id: str,
        x: float,
        y: float,
        *,
        yaw: float = 0.0,
        vx: float = 0.0,
        vy: float = 0.0,
        alive: bool = True,
    ) -> None:
        self.id = aid
        self.type_id = type_id
        self.is_alive = alive
        self._tf = _Tf(x, y, yaw)
        self._vel = _Vel(vx, vy)
        self.bounding_box = SimpleNamespace(extent=SimpleNamespace(x=2.25, y=0.9, z=0.7))

    def get_location(self) -> _Loc:
        return self._tf.location

    def get_transform(self) -> _Tf:
        return self._tf

    def get_velocity(self) -> _Vel:
        return self._vel


class _ActorList(list):
    def filter(self, pattern: str) -> _ActorList:
        import fnmatch

        return _ActorList(a for a in self if fnmatch.fnmatch(a.type_id, pattern))


class _Snap:
    def __init__(self, actors: list[_Actor]) -> None:
        self._m = {a.id: a for a in actors}

    def find(self, aid: int) -> _Actor | None:
        return self._m.get(int(aid))

    def __iter__(self):
        return iter(self._m.values())


class _World:
    def __init__(self, actors: list[_Actor], *, snapshot: bool = True) -> None:
        self._actors = _ActorList(actors)
        self._snapshot = snapshot
        self.get_actors_calls = 0
        self.get_actors_id_queries: list[list[int]] = []

    def get_actors(self, actor_ids: list[int] | None = None) -> _ActorList:
        self.get_actors_calls += 1
        if actor_ids is None:
            return self._actors
        want = {int(i) for i in actor_ids}
        self.get_actors_id_queries.append(list(want))
        return _ActorList(a for a in self._actors if int(a.id) in want)

    def get_snapshot(self) -> _Snap:
        if not self._snapshot:
            raise RuntimeError("no snapshot")
        return _Snap(list(self._actors))


def test_collect_dyn_ahead_vehicle() -> None:
    ego = _Actor(1, "vehicle.tesla.model3", 0.0, 0.0, vx=10.0)
    lead = _Actor(2, "vehicle.audi.tt", 25.0, 0.0, vx=8.0)
    world = _World([ego, lead])
    dyn = collect_dyn_objects(ego, world)
    assert dyn["dyn_n"] == 1
    assert dyn["vd_count"] == 1
    assert dyn["ped_count"] == 0
    assert dyn["cipv_id"] == 2
    assert dyn["obj0_id"] == 2
    assert dyn["obj0_long"] == pytest.approx(25.0, abs=0.05)
    assert dyn["obj0_lat"] == pytest.approx(0.0, abs=0.05)
    assert dyn["obj0_rel_v"] == pytest.approx(-2.0, abs=0.05)
    assert dyn["lead_from_dyn_long"] == pytest.approx(25.0, abs=0.05)


def test_collect_dyn_skips_ego_and_far() -> None:
    ego = _Actor(1, "vehicle.tesla.model3", 0.0, 0.0)
    far = _Actor(2, "vehicle.audi.tt", 200.0, 0.0)
    world = _World([ego, far])
    dyn = collect_dyn_objects(ego, world)
    assert dyn["dyn_n"] == 0
    assert dyn["cipv_id"] == 0


def test_collect_dyn_walker_and_no_snapshot() -> None:
    ego = _Actor(1, "vehicle.tesla.model3", 0.0, 0.0)
    ped = _Actor(3, "walker.pedestrian.0001", 10.0, 1.0)
    world = _World([ego, ped], snapshot=False)
    dyn = collect_dyn_objects(ego, world)
    assert dyn["dyn_n"] == 1
    assert dyn["ped_count"] == 1
    assert dyn["obj0_ped"] == 1
    assert dyn["obj0_long"] == pytest.approx(10.0, abs=0.05)


def test_collect_dyn_prefers_lead_id() -> None:
    ego = _Actor(1, "vehicle.tesla.model3", 0.0, 0.0)
    marked = _Actor(9, "vehicle.nissan.patrol", 12.0, 0.0)
    side = _Actor(2, "vehicle.audi.tt", 20.0, 3.5)
    world = _World([ego, marked, side])
    dyn = collect_dyn_objects(ego, world, lead=marked)
    assert dyn["dyn_n"] == 2
    assert dyn["obj0_long"] == pytest.approx(12.0, abs=0.05)
    assert dyn["obj0_id"] == 9
    assert dyn["cipv_id"] == 9


def test_dyn_cache_second_tick_skips_full_get_actors() -> None:
    ego = _Actor(1, "vehicle.tesla.model3", 0.0, 0.0, vx=10.0)
    lead = _Actor(2, "vehicle.audi.tt", 25.0, 0.0, vx=8.0)
    world = _World([ego, lead])
    collect_dyn_objects(ego, world)
    assert world.get_actors_calls == 1
    lead._tf.location.x = 24.0
    dyn = collect_dyn_objects(ego, world)
    assert world.get_actors_calls == 1
    assert world.get_actors_id_queries == []
    assert dyn["obj0_long"] == pytest.approx(24.0, abs=0.05)


def test_dyn_cache_fetches_only_new_id() -> None:
    ego = _Actor(1, "vehicle.tesla.model3", 0.0, 0.0)
    a = _Actor(2, "vehicle.audi.tt", 20.0, 3.5)
    world = _World([ego, a])
    collect_dyn_objects(ego, world)
    b = _Actor(5, "vehicle.nissan.patrol", 15.0, 0.0)
    world._actors.append(b)
    dyn = collect_dyn_objects(ego, world)
    assert world.get_actors_calls == 2
    assert world.get_actors_id_queries == [[5]]
    assert dyn["dyn_n"] == 2
    assert {dyn["obj0_id"], dyn["obj1_id"]} == {5, 2}


def test_obj_id_follows_actor_not_slot() -> None:
    """Adding a nearer host car must not recolor an adjacent-lane object."""
    ego = _Actor(1, "vehicle.tesla.model3", 0.0, 0.0)
    side = _Actor(20, "vehicle.audi.tt", 30.0, 3.5)
    world = _World([ego, side])
    first = collect_dyn_objects(ego, world)
    assert first["obj0_id"] == 20
    near = _Actor(7, "vehicle.nissan.patrol", 15.0, 0.0)
    world._actors.append(near)
    second = collect_dyn_objects(ego, world)
    by_id = {second["obj0_id"]: second["obj0_long"], second["obj1_id"]: second["obj1_long"]}
    assert by_id[20] == pytest.approx(30.0, abs=0.05)
    assert by_id[7] == pytest.approx(15.0, abs=0.05)


def test_optic_in_wedge() -> None:
    assert optic_in_wedge(20.0, 0.0)
    assert not optic_in_wedge(-8.0, 0.0)
    assert not optic_in_wedge(0.0, 5.0)
    assert not optic_in_wedge(10.0, 20.0)


def test_collect_dyn_skips_rear_and_wide_bearing() -> None:
    ego = _Actor(1, "vehicle.tesla.model3", 0.0, 0.0)
    rear = _Actor(2, "vehicle.audi.tt", -12.0, 0.0)
    wide = _Actor(3, "vehicle.nissan.patrol", 15.0, 30.0)
    world = _World([ego, rear, wide])
    dyn = collect_dyn_objects(ego, world)
    assert dyn["dyn_n"] == 0


def test_collect_dyn_drops_occluded_host() -> None:
    ego = _Actor(1, "vehicle.tesla.model3", 0.0, 0.0)
    occ = _Actor(2, "vehicle.audi.tt", 12.0, 0.0)
    hidden = _Actor(3, "vehicle.nissan.patrol", 30.0, 0.0)
    side = _Actor(4, "vehicle.bmw.grandtourer", 28.0, 3.5)
    world = _World([ego, occ, hidden, side])
    dyn = collect_dyn_objects(ego, world)
    ids = {dyn[f"obj{i}_id"] for i in range(dyn["dyn_n"])}
    assert 2 in ids
    assert 3 not in ids
    assert 4 in ids


def test_drop_host_behind_occupy_keeps_adjacent() -> None:
    items = [
        {"lat_m": 0.0, "long_m": 12.0},
        {"lat_m": 0.0, "long_m": 30.0},
        {"lat_m": 3.5, "long_m": 28.0},
    ]
    out = drop_host_behind_occupy(items)
    assert [it["long_m"] for it in out] == [12.0, 28.0]
