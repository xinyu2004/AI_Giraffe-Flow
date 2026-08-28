"""PerfAgg smoke (no CARLA)."""

from __future__ import annotations

import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[1] / "src" / "lib"
sys.path.insert(0, str(_LIB))

from _perf import PerfAgg, perf_enabled  # noqa: E402
from _view import scenario_view_wanted  # noqa: E402


def test_scenario_view_wanted(monkeypatch) -> None:
    monkeypatch.setenv("GF_SCENARIO_VIEW", "0")
    assert scenario_view_wanted() is False
    monkeypatch.setenv("GF_SCENARIO_VIEW", "1")
    assert scenario_view_wanted() is True


def test_perf_agg_prints(capsys) -> None:
    assert perf_enabled() in (True, False)
    p = PerfAgg("t")
    p.add("work", 0.01)
    p.count("ue_frame")
    p._last = p._last - 3.0  # force flush
    p.tick(extra={"k": "1"})
    out = capsys.readouterr().out
    if perf_enabled():
        assert "[perf][t]" in out
        assert "work=" in out
        assert "ue_frame=" in out
