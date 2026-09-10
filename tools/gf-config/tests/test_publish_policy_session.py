"""Publish policy helpers: keyed by topic short name; Outs drive the set."""

from __future__ import annotations

from gf_config.core import ProjectSession, default_publish_spec


def _session() -> ProjectSession:
    s = object.__new__(ProjectSession)
    s.req = {
        "publish_policy": {
            "services": {
                "EgoMotion": {"trigger": "period", "period_ms": 10},
                "Trajectory": {"trigger": "on_change"},
            },
            "channels": {"vehicle_cmd": {"trigger": "period", "period_ms": 10}},
        },
        "frame_ingest": {
            "channels": {
                "vehicle_cmd": "gf.channel.vehicle_cmd",
                "surround_world": "gf.channel.surround_world",
            }
        },
    }
    s.wiring = {
        "deployments": [
            {
                "process": "adapter.vehicle_can_gateway",
                "provides": [
                    "services.semantic.EgoMotion",
                    "services.semantic.Trajectory",
                ],
                "requires": [],
            },
            {
                "process": "planning.driving",
                "provides": ["services.semantic.Trajectory"],
                "requires": [],
            },
            {
                "process": "mode.drive_park",
                "provides": ["services.semantic.VehicleMode"],
                "requires": [],
            },
        ],
        "dataflows": [],
        "channel_flows": [],
        "canvas": {"nodes": {}},
    }
    s.dirty_wiring = False
    s.dirty_req = False
    return s


def test_two_modules_may_out_same_short() -> None:
    s = _session()
    shorts = s.provided_service_shorts()
    assert shorts.count("Trajectory") == 1  # set of providers, listed once
    assert "EgoMotion" in shorts and "VehicleMode" in shorts


def test_apply_out_policies_shared_by_short() -> None:
    s = _session()
    s.apply_out_publish_policies(
        {"Trajectory": {"trigger": "on_change", "expect_fps": 15}}
    )
    assert s.service_publish_spec("Trajectory")["expect_fps"] == 15
    # Still one topic entry even though two modules Out Trajectory
    assert "Trajectory" in s.publish_policy_services()


def test_prune_orphan_policy() -> None:
    s = _session()
    s.req["publish_policy"]["services"]["Orphan"] = {"trigger": "on_change"}
    s.prune_orphan_publish_policies()
    assert "Orphan" not in s.publish_policy_services()
    assert "EgoMotion" in s.publish_policy_services()


def test_channel_policy_names_from_frame_ingest() -> None:
    s = _session()
    names = s.channel_policy_names()
    assert "vehicle_cmd" in names
    assert "surround_world" in names


def test_apply_channel_publish_policies() -> None:
    s = _session()
    s.apply_channel_publish_policies(
        {"vehicle_cmd": {"trigger": "period", "period_ms": 20}}
    )
    assert s.publish_policy_channels()["vehicle_cmd"]["period_ms"] == 20
    s.apply_channel_publish_policies({"fake_perc": {"trigger": "on_change"}})
    assert list(s.publish_policy_channels().keys()) == ["fake_perc"]


def test_default_publish_spec() -> None:
    assert default_publish_spec()["trigger"] == "on_change"
    assert default_publish_spec(trigger="period")["period_ms"] == 10
