"""ChaseCam occluder ghost — lab Cam 2/3/4 (elevated spectators).

Hide Bridge/Roads that block seeing the ego: tube|screen seed, then the whole
connected overhead span. Camera pose never changes. Catalog once per world.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

_EVERY_N = 3
_T_CLEAR = 12
_TUBE_R = 2.7
_SAMPLES = 10
_T_LO = 0.05
_T_HI = 0.90
_Z_LO_ABOVE_EGO = 1.0
_Z_HI_BELOW_CAM = 1.0
_FOOTING_Z = 2.0
_NEAR_M = 65.0
_LINK_PAD = 10.0
_MAX_COMPS = 2
_SOFT_CAP = 64

_LABELS = ("Bridge", "Roads")
_CATALOGS: Dict[int, "_Catalog"] = {}


def chase_ghost_wanted() -> bool:
    v = (os.environ.get("GF_CHASE_GHOST_OCCLUDERS") or "1").strip().lower()
    return v not in ("0", "off", "false", "no")


def _enum(mod: Any, name: str) -> Any:
    return getattr(mod.CityObjectLabel, name, None)


def _d2(ax: float, ay: float, bx: float, by: float) -> float:
    return (ax - bx) ** 2 + (ay - by) ** 2


def _lerp(carla: Any, a: Any, b: Any, t: float) -> Any:
    return carla.Location(
        x=a.x + (b.x - a.x) * t,
        y=a.y + (b.y - a.y) * t,
        z=a.z + (b.z - a.z) * t,
    )


def _contains(carla: Any, bb: Any, tf: Any, p: Any) -> bool:
    try:
        if bb.contains(p, carla.Transform()):
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        return bool(bb.contains(p, tf))
    except Exception:  # noqa: BLE001
        return False


@dataclass(frozen=True)
class _Mesh:
    id: int
    cx: float
    cy: float
    cz: float
    zmin: float
    zmax: float
    rad: float
    raw: Any


class _Catalog:
    __slots__ = ("meshes", "built")

    def __init__(self) -> None:
        self.meshes: List[_Mesh] = []
        self.built = False

    def build(self, world: Any, labels: List[Any]) -> None:
        if self.built:
            return
        out: List[_Mesh] = []
        for lab in labels:
            try:
                objs = world.get_environment_objects(lab) or ()
            except Exception:  # noqa: BLE001
                continue
            for obj in objs:
                try:
                    oid = int(obj.id)
                    tf, bb = obj.transform, obj.bounding_box
                    c = tf.location
                    rad = max(float(bb.extent.x), float(bb.extent.y))
                    try:
                        zs = [float(v.z) for v in bb.get_world_vertices(tf)]
                        z0, z1 = min(zs), max(zs)
                    except Exception:  # noqa: BLE001
                        e = float(bb.extent.z)
                        z0, z1 = float(c.z) - e, float(c.z) + e
                    out.append(
                        _Mesh(oid, float(c.x), float(c.y), float(c.z), z0, z1, rad, obj)
                    )
                except Exception:  # noqa: BLE001
                    continue
        self.meshes = out
        self.built = True


def _cat_for(world: Any) -> _Catalog:
    key = id(world)
    cat = _CATALOGS.get(key)
    if cat is None:
        cat = _Catalog()
        _CATALOGS[key] = cat
    return cat


def _drop_cat(world: Any) -> None:
    _CATALOGS.pop(id(world), None)


def _components(cands: List[_Mesh]) -> List[Set[int]]:
    parent = {m.id: m.id for m in cands}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i, a in enumerate(cands):
        for b in cands[i + 1 :]:
            lim = a.rad + b.rad + _LINK_PAD
            if _d2(a.cx, a.cy, b.cx, b.cy) <= lim * lim:
                union(a.id, b.id)

    groups: Dict[int, Set[int]] = {}
    for m in cands:
        groups.setdefault(find(m.id), set()).add(m.id)
    return list(groups.values())


class ChaseGhostOccluders:
    """Hide connected Bridge/Roads span between ChaseCam and ego."""

    def __init__(self, world: Any, carla_mod: Any) -> None:
        self._world = world
        self._carla = carla_mod
        self._on = chase_ghost_wanted()
        self._hidden: Set[int] = set()
        self._sticky: Set[int] = set()
        self._miss: Dict[int, int] = {}
        self._frame = 0
        self._cat = _cat_for(world)
        self._labels: List[Any] = []
        if self._on:
            for name in _LABELS:
                e = _enum(carla_mod, name)
                if e is not None:
                    self._labels.append(e)
            if not self._labels:
                self._on = False

    def _ensure(self) -> None:
        if not self._cat.built and self._labels:
            self._cat.build(self._world, self._labels)

    def _footing(self, m: _Mesh, focus: Any) -> bool:
        return m.zmax <= float(focus.z) + _FOOTING_Z

    def _overhead_band(self, m: _Mesh, ego_z: float, cam_z: float) -> bool:
        lo = ego_z + _Z_LO_ABOVE_EGO
        hi = cam_z - _Z_HI_BELOW_CAM
        if hi <= lo:
            hi = cam_z
        return m.zmax >= lo and m.zmin <= hi

    def _tube_hit(self, m: _Mesh, cam: Any, focus: Any) -> Optional[float]:
        carla = self._carla
        bb, tf = m.raw.bounding_box, m.raw.transform
        best: Optional[float] = None
        for i in range(_SAMPLES + 1):
            t = i / float(_SAMPLES)
            if t < _T_LO or t > _T_HI:
                continue
            p = _lerp(carla, cam, focus, t)
            hit = _contains(carla, bb, tf, p)
            if not hit:
                for dx, dy in (
                    (_TUBE_R, 0.0),
                    (-_TUBE_R, 0.0),
                    (0.0, _TUBE_R),
                    (0.0, -_TUBE_R),
                    (_TUBE_R * 0.7, _TUBE_R * 0.7),
                    (-_TUBE_R * 0.7, _TUBE_R * 0.7),
                ):
                    q = carla.Location(x=p.x + dx, y=p.y + dy, z=p.z)
                    if _contains(carla, bb, tf, q):
                        hit = True
                        break
            if hit:
                best = t if best is None else min(best, t)
        return best

    def _in_frustum(
        self,
        inv: Any,
        x: float,
        y: float,
        z: float,
        half: float,
        v_half: float,
    ) -> bool:
        # CARLA camera local: +X forward, +Y right, +Z up (not OpenGL z-depth).
        rx = inv[0][0] * x + inv[0][1] * y + inv[0][2] * z + inv[0][3]
        ry = inv[1][0] * x + inv[1][1] * y + inv[1][2] * z + inv[1][3]
        rz = inv[2][0] * x + inv[2][1] * y + inv[2][2] * z + inv[2][3]
        if rx < 1.0:
            return False
        if abs(ry) > half * rx * 0.95:
            return False
        if abs(rz) > v_half * rx * 0.85:
            return False
        return True

    def _screen_hit(self, m: _Mesh, cam_tf: Any, fov_deg: float, aspect: float) -> bool:
        try:
            inv = cam_tf.get_inverse_matrix()
        except Exception:  # noqa: BLE001
            return False
        half = math.tan(math.radians(0.5 * fov_deg))
        v_half = half / max(aspect, 0.5)
        if self._in_frustum(inv, m.cx, m.cy, m.cz, half, v_half):
            return True
        try:
            verts = m.raw.bounding_box.get_world_vertices(m.raw.transform)
        except Exception:  # noqa: BLE001
            return False
        for v in verts:
            if self._in_frustum(inv, float(v.x), float(v.y), float(v.z), half, v_half):
                return True
        return False

    def _seed_score(
        self,
        m: _Mesh,
        cam: Any,
        cam_tf: Any,
        focus: Any,
        fov: float,
        aspect: float,
    ) -> Optional[float]:
        # Primary: in the chase view (overpass ahead of ego). Tube is cam→ego only.
        if self._screen_hit(m, cam_tf, fov, aspect):
            return 0.55
        return self._tube_hit(m, cam, focus)

    def _select(self, camera: Any, vehicle: Any) -> Set[int]:
        carla = self._carla
        try:
            cam_tf = camera.get_transform()
            cam = cam_tf.location
            ego = vehicle.get_location()
            focus = carla.Location(x=ego.x, y=ego.y, z=ego.z + 1.45)
        except Exception:  # noqa: BLE001
            return set()

        fov = 78.0
        aspect = 16.0 / 9.0
        try:
            fov = float(camera.attributes.get("fov", fov))
            w = float(camera.attributes.get("image_size_x", 960))
            h = float(camera.attributes.get("image_size_y", 540))
            if h > 1:
                aspect = w / h
        except Exception:  # noqa: BLE001
            pass

        ego_z, cam_z = float(ego.z), float(cam.z)
        cx, cy = float(cam.x), float(cam.y)
        ex, ey = float(ego.x), float(ego.y)
        lim2 = _NEAR_M * _NEAR_M

        cands: List[_Mesh] = []
        seeds: Dict[int, float] = {}
        for m in self._cat.meshes:
            if self._footing(m, focus):
                continue
            if not self._overhead_band(m, ego_z, cam_z):
                continue
            if _d2(m.cx, m.cy, cx, cy) > lim2 and _d2(m.cx, m.cy, ex, ey) > lim2:
                continue
            cands.append(m)
            sc = self._seed_score(m, cam, cam_tf, focus, fov, aspect)
            if sc is not None:
                seeds[m.id] = sc

        if not seeds or not cands:
            return set()

        ranked: List[Tuple[float, Set[int]]] = []
        for g in _components(cands):
            ts = [seeds[i] for i in g if i in seeds]
            if ts:
                ranked.append((min(ts), g))
        ranked.sort(key=lambda x: x[0])

        out: Set[int] = set()
        n_ids = 0
        for _t, g in ranked[:_MAX_COMPS]:
            if n_ids + len(g) > _SOFT_CAP and out:
                break
            out |= g
            n_ids += len(g)
            if n_ids >= _SOFT_CAP:
                break
        return out

    def _held(self, S: Set[int]) -> Set[int]:
        for oid in S:
            self._miss[oid] = 0
        tracked = set(self._hidden) | set(self._miss) | S | self._sticky
        for oid in tracked:
            if oid in S:
                continue
            self._miss[oid] = self._miss.get(oid, 0) + 1
        held = {oid for oid, n in self._miss.items() if n < _T_CLEAR}
        self._miss = {oid: n for oid, n in self._miss.items() if n < _T_CLEAR}
        return held

    def pump(self, *, mode: str, camera: Any, vehicle: Any) -> None:
        if not self._on:
            return
        if mode not in ("2", "3", "4"):
            self.restore_all()
            return
        self._frame += 1
        if (self._frame % _EVERY_N) != 0:
            return
        if camera is None or vehicle is None:
            return

        self._ensure()
        S = self._select(camera, vehicle)
        if S:
            if self._sticky and (S & self._sticky):
                S = S | self._sticky
            self._sticky = set(S)
        self._apply(self._held(S))

    def restore_all(self) -> None:
        if self._hidden:
            self._set(self._hidden, True)
        self._hidden.clear()
        self._sticky.clear()
        self._miss.clear()

    def destroy(self) -> None:
        self.restore_all()
        self._on = False
        _drop_cat(self._world)

    def _apply(self, want: Set[int]) -> None:
        if want == self._hidden:
            return
        hide = want - self._hidden
        show = self._hidden - want
        if hide:
            self._set(hide, False)
        if show:
            self._set(show, True)
        self._hidden = set(want)

    def _set(self, ids: Set[int], enable: bool) -> None:
        if not ids:
            return
        try:
            self._world.enable_environment_objects(set(ids), enable)
        except Exception:  # noqa: BLE001
            return


__all__ = ["ChaseGhostOccluders", "chase_ghost_wanted"]
