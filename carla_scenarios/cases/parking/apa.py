#!/usr/bin/env python3
"""APA — Town04 lot; write gold P* for slot 2, confirm after stop."""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
_LIB = _SRC / "lib"
for _p in (_ROOT, _SRC, _LIB, Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

os.environ.setdefault("GF_CHASE_CAM", "3")

from _case_atom import AtomCase, bind_run_session  # noqa: E402
from _mode_hint import write_mode_hint  # noqa: E402
from _objects_truth import _xy_to_ego  # noqa: E402
from _surround_truth import collect_surround_world  # noqa: E402
from layouts.parking_lot import layout_parking_lot  # noqa: E402

_SPOT_MAX_MPS = 15.0 / 3.6
_CONFIRM_AFTER_S = 6.0
_STOP_MPS = 0.35


def _ego_corners(ego, p_world):
    tf = ego.get_transform()
    yaw = math.radians(float(tf.rotation.yaw))
    c, s = math.cos(yaw), math.sin(yaw)
    ex, ey = float(tf.location.x), float(tf.location.y)
    out = []
    for wx, wy in p_world:
        out.extend(_xy_to_ego(ex, ey, c, s, float(wx), float(wy)))
    return out


def _on_tick(elapsed, ego, target, meta, cmd):
    del target, cmd
    try:
        vel = ego.get_velocity()
        v = math.sqrt(vel.x**2 + vel.y**2 + vel.z**2)
    except Exception:  # noqa: BLE001
        v = 0.0
    p_world = meta.get("pick_p_world") or ((0, 0), (0, 0), (0, 0))
    p0x, p0y, p1x, p1y, p2x, p2y = _ego_corners(ego, p_world)
    apa = 1 if v < _SPOT_MAX_MPS else 0
    confirm = 1 if (elapsed >= _CONFIRM_AFTER_S and v < _STOP_MPS) else 0
    write_mode_hint(
        apa_armed=apa,
        slot_confirmed=confirm,
        fParkingSlot_P0X=p0x,
        fParkingSlot_P0Y=p0y,
        fParkingSlot_P1X=p1x,
        fParkingSlot_P1Y=p1y,
        fParkingSlot_P2X=p2x,
        fParkingSlot_P2Y=p2y,
    )
    meta["p2_ego"] = (p0x, p0y, p1x, p1y, p2x, p2y)
    try:
        sw = collect_surround_world(ego, ego.get_world())
        slot2 = next(
            (s for s in sw.get("slots") or [] if int(s.get("slot_id") or 0) == 2),
            None,
        )
        meta["slot2_free"] = int(slot2.get("free") or 0) if slot2 else 0
        meta["n_slot"] = int(sw.get("n_slot") or 0)
        if slot2:
            meta["slot2_xy"] = (
                float(slot2.get("center_x_m") or 0.0),
                float(slot2.get("center_y_m") or 0.0),
            )
    except Exception:  # noqa: BLE001
        pass
    if confirm:
        meta["confirmed"] = 1
    if confirm and elapsed < _CONFIRM_AFTER_S + 0.3:
        print(f"[apa] ModeHint confirm slot=2 v={v:.2f} t={elapsed:.1f}", flush=True)


def _judge(samples, seen, meta):
    del samples, seen
    n_slot = int(meta.get("n_slot") or 0)
    if n_slot < 2:
        return False, "no_pld_slots", {"n_slot": n_slot}
    if int(meta.get("slot2_free") or 0) != 1:
        return False, "slot2_not_free", {"slot2_free": meta.get("slot2_free")}
    p = meta.get("p2_ego") or ()
    if len(p) != 6 or sum(abs(float(x)) for x in p) < 0.5:
        return False, "no_p_corners", {}
    # SlotFromP center = mid(P0, P2); must land on gold slot 2, not another bay.
    cx = 0.5 * (float(p[0]) + float(p[4]))
    cy = 0.5 * (float(p[1]) + float(p[5]))
    s2 = meta.get("slot2_xy") or (None, None)
    if s2[0] is None:
        return False, "no_slot2_xy", {"n_slot": n_slot}
    dist = math.hypot(cx - float(s2[0]), cy - float(s2[1]))
    if dist > 1.5:
        return False, "p_not_slot2", {
            "dist_m": round(dist, 2),
            "p_center": [round(cx, 2), round(cy, 2)],
            "slot2_xy": [round(float(s2[0]), 2), round(float(s2[1]), 2)],
        }
    if int(meta.get("confirmed") or 0) != 1:
        return False, "not_confirmed", {"note": "apa must confirm after stop"}
    return True, "ok", {
        "note": "planning P* triangle is slot 2",
        "n_slot": n_slot,
        "p_center": [round(cx, 2), round(cy, 2)],
        "dist_m": round(dist, 2),
    }


CASE = AtomCase(
    tag="apa",
    layout=layout_parking_lot,
    judge=_judge,
    weather_preset=None,
    early_exit_on_collision=False,
    on_tick=_on_tick,
    title="Parking APA (Town04 lot, pick slot 2 via P*)",
    default_duration_s=20.0,
)

run_session = bind_run_session(CASE)

if __name__ == "__main__":
    raise SystemExit(CASE.main())
