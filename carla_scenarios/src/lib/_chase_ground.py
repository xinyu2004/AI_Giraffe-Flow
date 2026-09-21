"""UE ChaseCam framing: place ego on screen, keep lab mount distance.

Along-ray scale sets apparent size (mode 3 pulled in). Mode 2 slides
forward along +x, then drops in z with pitch held fixed.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

# mode → where ego sits in the image (NDC y: +1 top, -1 bottom)
PROFILE_EGO_REAR = "ego_rear"  # ChaseCam=2: ego near the bottom
PROFILE_BALANCED = "balanced"  # ChaseCam=3: ego near vertical center
_NDC_EGO_REAR = -0.78  # ChaseCam=2: ego low, little rear on screen
_NDC_BALANCED = -0.05  # ChaseCam=3: near vertical center
_K_EGO_REAR = 1.0
_K_BALANCED = 0.70  # mode 3 pulled in along the mount ray
# Mode 2: slide forward along +x so UE can pitch down onto the road
# (shallow pitch at x=-35 left D_fwd=0 → "already past the bridge").
_FWD_SHIFT_EGO_REAR = 15.0
_FWD_SHIFT_BALANCED = 0.0
# Mode 2: rigid nudge after pitch is fixed (do not re-aim).
_Z_DROP_EGO_REAR = 24.0
_Z_DROP_BALANCED = 0.0
_POST_FWD_EGO_REAR = 9.8
_POST_FWD_BALANCED = 0.0


def vfov_deg(hfov_deg: float, aspect: float) -> float:
    """Vertical FOV from horizontal FOV and width/height aspect."""
    if aspect <= 1.0e-6:
        return float(hfov_deg)
    h = math.radians(float(hfov_deg))
    return math.degrees(2.0 * math.atan(math.tan(0.5 * h) / aspect))


def ground_hit_x(
    cx: float,
    cz: float,
    pitch_deg: float,
    hfov_deg: float,
    aspect: float,
    *,
    edge: str,
) -> Optional[float]:
    """Ego-frame ground hit x for top/bottom frustum edge (yaw=0, y=0 plane).

    CARLA/UE: +x forward, +z up; pitch>0 looks up. Camera at (cx,0,cz).
    """
    pitch = math.radians(float(pitch_deg))
    vhalf = math.radians(0.5 * vfov_deg(hfov_deg, aspect))
    ax = math.cos(pitch)
    az = math.sin(pitch)
    ux = -math.sin(pitch)
    uz = math.cos(pitch)
    s = 1.0 if edge == "top" else -1.0
    tana = math.tan(vhalf)
    dx = ax + s * tana * ux
    dz = az + s * tana * uz
    n = math.hypot(dx, dz)
    if n < 1.0e-9:
        return None
    dx /= n
    dz /= n
    if dz >= -1.0e-6:
        return None
    t = -float(cz) / dz
    if t <= 0.0:
        return None
    return float(cx) + t * dx


def ground_extents(
    cx: float,
    cz: float,
    pitch_deg: float,
    hfov_deg: float,
    aspect: float,
) -> Tuple[float, float]:
    """Return (D_fwd_m, D_rear_m) along ego +x from frustum ∩ ground."""
    x_top = ground_hit_x(cx, cz, pitch_deg, hfov_deg, aspect, edge="top")
    x_bot = ground_hit_x(cx, cz, pitch_deg, hfov_deg, aspect, edge="bottom")
    d_fwd = 0.0 if x_top is None else max(0.0, x_top)
    d_rear = 0.0 if x_bot is None else max(0.0, -x_bot)
    return d_fwd, d_rear


def ego_screen_y(
    cx: float,
    cz: float,
    pitch_deg: float,
    hfov_deg: float,
    aspect: float,
) -> Optional[float]:
    """NDC y of the ego origin. +1 is the top of the frame, -1 the bottom.

    Independent of range along the same ray (cx, cz) ∝ (mx, mz).
    """
    pitch = math.radians(float(pitch_deg))
    fx, fz = math.cos(pitch), math.sin(pitch)
    ux, uz = -math.sin(pitch), math.cos(pitch)
    vx, vz = -float(cx), -float(cz)
    depth = vx * fx + vz * fz
    if depth <= 1.0e-6:
        return None
    up = vx * ux + vz * uz
    t = math.tan(math.radians(0.5 * vfov_deg(hfov_deg, aspect)))
    if t < 1.0e-9:
        return None
    return up / (depth * t)


def target_ego_ndc(profile: str) -> float:
    """Screen anchor: 2 below center, 3 near center."""
    if profile == PROFILE_BALANCED:
        return _NDC_BALANCED
    return _NDC_EGO_REAR


def distance_scale(profile: str) -> float:
    """Along-ray scale. Does not move ego on screen; only apparent size."""
    if profile == PROFILE_BALANCED:
        return _K_BALANCED
    return _K_EGO_REAR


def forward_shift(profile: str) -> float:
    """Extra +x (m) after scale. Mode 2 slides forward for road-ahead pitch."""
    if profile == PROFILE_BALANCED:
        return _FWD_SHIFT_BALANCED
    return _FWD_SHIFT_EGO_REAR


def z_drop(profile: str) -> float:
    """World-down shift (m) after pitch is fixed. Does not re-aim."""
    if profile == PROFILE_BALANCED:
        return _Z_DROP_BALANCED
    return _Z_DROP_EGO_REAR


def post_forward(profile: str) -> float:
    """Extra +x (m) after pitch is fixed. Pulls the rear ground out of frame."""
    if profile == PROFILE_BALANCED:
        return _POST_FWD_BALANCED
    return _POST_FWD_EGO_REAR


def solve_spectator_along_mount(
    mx: float,
    mz: float,
    pitch_rgb: float,
    hfov_rgb: float,
    aspect: float,
    hfov_ue: float,
    *,
    profile: str = PROFILE_EGO_REAR,
    pitch_lo: float = -75.0,
    pitch_hi: float = -8.0,
) -> Tuple[float, float, float, float, float]:
    """Place ego on screen; optional forward slide + distance scale.

    Returns (sx, sz, pitch_ue, ego_ndc, ndc_err).
    """
    lab_pitch = float(pitch_rgb)
    del hfov_rgb, pitch_rgb  # screen target does not use pygame FOV/pitch
    k = distance_scale(profile)
    sx = float(mx) * k + forward_shift(profile)
    sz = float(mz) * k
    if sz < 1.0:
        return sx, sz, lab_pitch, 0.0, 0.0
    tgt = target_ego_ndc(profile)
    lo, hi = float(pitch_lo), float(pitch_hi)
    # More negative pitch looks further down → ego climbs the frame.
    y_lo = ego_screen_y(sx, sz, lo, hfov_ue, aspect)
    y_hi = ego_screen_y(sx, sz, hi, hfov_ue, aspect)
    if y_lo is None or y_hi is None:
        return sx, sz, lab_pitch, 0.0, 0.0
    if tgt >= y_lo:
        pitch = lo
    elif tgt <= y_hi:
        pitch = hi
    else:
        for _ in range(24):
            mid = 0.5 * (lo + hi)
            y = ego_screen_y(sx, sz, mid, hfov_ue, aspect)
            if y is None or y > tgt:
                lo = mid
            else:
                hi = mid
        pitch = 0.5 * (lo + hi)
    drop = z_drop(profile)
    sx_view = sx + post_forward(profile)
    sz_view = sz - drop
    y = ego_screen_y(sx_view, sz_view, pitch, hfov_ue, aspect)
    if y is None:
        return sx_view, sz_view, pitch, 0.0, 0.0
    return sx_view, sz_view, pitch, y, y - tgt


def profile_for_mode(mode: str) -> str:
    if mode == "3":
        return PROFILE_BALANCED
    return PROFILE_EGO_REAR
