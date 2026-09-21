"""Unit tests for ChaseCam ground-footprint matching (no CARLA)."""

from __future__ import annotations

from _chase_ground import (
    PROFILE_BALANCED,
    PROFILE_EGO_REAR,
    distance_scale,
    ego_screen_y,
    ground_extents,
    ground_hit_x,
    profile_for_mode,
    solve_spectator_along_mount,
    target_ego_ndc,
    vfov_deg,
)


def test_vfov_landscape() -> None:
    v = vfov_deg(60.0, 16.0 / 9.0)
    assert 34.0 < v < 38.0


def test_ground_hit_looks_down() -> None:
    x_bot = ground_hit_x(-35.0, 40.0, -33.0, 60.0, 16.0 / 9.0, edge="bottom")
    x_top = ground_hit_x(-35.0, 40.0, -33.0, 60.0, 16.0 / 9.0, edge="top")
    assert x_bot is not None and x_top is not None
    assert x_bot < x_top


def test_extents_positive() -> None:
    fwd, rear = ground_extents(-35.0, 40.0, -33.0, 60.0, 16.0 / 9.0)
    assert fwd > 1.0
    assert rear >= 0.0


def test_profiles() -> None:
    assert profile_for_mode("2") == PROFILE_EGO_REAR
    assert profile_for_mode("3") == PROFILE_BALANCED
    assert target_ego_ndc(PROFILE_EGO_REAR) == -0.78
    assert target_ego_ndc(PROFILE_BALANCED) == -0.05
    assert distance_scale(PROFILE_EGO_REAR) == 1.0
    assert distance_scale(PROFILE_BALANCED) == 0.70


def test_pygame_ego_screen() -> None:
    aspect = 960.0 / 540.0
    y2 = ego_screen_y(-35.0, 40.0, -33.0, 60.0, aspect)
    y3 = ego_screen_y(-60.0, 62.0, -44.0, 72.0, aspect)
    assert y2 is not None and y2 < -0.7
    assert y3 is not None and abs(y3) < 0.25


def test_solve_ego_rear() -> None:
    aspect = 960.0 / 540.0
    mx, mz, pitch, fov = -35.0, 40.0, -33.0, 60.0
    sx, sz, pue, ndc, err = solve_spectator_along_mount(
        mx, mz, pitch, fov, aspect, 100.0, profile=PROFILE_EGO_REAR
    )
    # Aim unchanged, then nudge so far ground is ~450 m and rear stays ~4 m.
    assert abs(sx - (mx + 24.8)) < 1.0e-9 and abs(sz - (mz - 24.0)) < 1.0e-9
    aimed = ego_screen_y(mx + 15.0, mz, pue, 100.0, aspect)
    assert aimed is not None and abs(aimed - target_ego_ndc(PROFILE_EGO_REAR)) < 0.02
    got = ego_screen_y(sx, sz, pue, 100.0, aspect)
    assert got is not None and abs(ndc - got) < 1.0e-9
    fwd, rear = ground_extents(sx, sz, pue, 100.0, aspect)
    assert 430.0 < fwd < 470.0
    assert abs(rear - 4.3) < 0.4


def test_solve_balanced_near_center() -> None:
    aspect = 960.0 / 540.0
    mx, mz, pitch, fov = -60.0, 62.0, -44.0, 72.0
    sx, sz, pue, ndc, err = solve_spectator_along_mount(
        mx, mz, pitch, fov, aspect, 100.0, profile=PROFILE_BALANCED
    )
    assert abs(sx - mx * 0.70) < 1.0e-6
    assert abs(sz - mz * 0.70) < 1.0e-6
    assert abs(ndc - target_ego_ndc(PROFILE_BALANCED)) < 0.02
    assert abs(err) < 0.02
    assert pue > -70.0
