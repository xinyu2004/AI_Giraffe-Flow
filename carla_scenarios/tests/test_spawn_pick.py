"""Unit tests for spawn.pick (no CARLA world)."""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
_LIB = _SRC / "lib"
for _p in (_SRC, _LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from spawn.pick import prefer_center_lane  # noqa: E402


class _Wp:
    def __init__(self, lane_id: int, *, left: "_Wp | None" = None, right: "_Wp | None" = None):
        self.lane_id = lane_id
        self._left = left
        self._right = right
        try:
            import carla  # type: ignore

            self.lane_type = carla.LaneType.Driving
        except Exception:  # noqa: BLE001
            self.lane_type = 2

    def get_left_lane(self) -> "_Wp | None":
        return self._left

    def get_right_lane(self) -> "_Wp | None":
        return self._right


def _chain(*ids: int) -> list[_Wp]:
    wps = [_Wp(i) for i in ids]
    for i, wp in enumerate(wps):
        wp._left = wps[i - 1] if i else None
        wp._right = wps[i + 1] if i + 1 < len(wps) else None
    return wps


def test_prefer_center_three_lanes_not_leftmost() -> None:
    left, mid, right = _chain(1, 2, 3)
    assert prefer_center_lane(left) is mid
    assert prefer_center_lane(mid) is mid
    assert prefer_center_lane(right) is mid


def test_prefer_center_two_lanes_picks_non_left() -> None:
    left, right = _chain(10, 20)
    assert prefer_center_lane(left) is right
    assert prefer_center_lane(right) is right


def test_prefer_center_single_lane() -> None:
    only = _chain(7)[0]
    assert prefer_center_lane(only) is only
