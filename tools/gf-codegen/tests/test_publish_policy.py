from __future__ import annotations

from gf_codegen.compose.publish_policy import (
    apply_publish_policy,
    camera_fps_ceiling,
    emit_publish_policy_hpp,
    normalize_policy,
)


def test_normalize_nested_and_flat() -> None:
    nested = normalize_policy(
        {
            "publish_policy": {
                "services": {"EgoMotion": {"trigger": "period", "period_ms": 10}},
                "channels": {"fake_perc": {"trigger": "on_change"}},
            }
        }
    )
    assert nested["services"]["EgoMotion"]["period_ms"] == 10
    assert nested["channels"]["fake_perc"]["trigger"] == "on_change"

    flat = normalize_policy(
        {
            "publish_policy": {
                "EgoMotion": {"trigger": "period", "period_ms": 10},
                "vehicle_cmd": {"trigger": "period", "period_ms": 10},
            }
        }
    )
    assert "EgoMotion" in flat["services"]
    assert "vehicle_cmd" in flat["channels"]


def test_apply_stamps_services_and_drops_invented_period() -> None:
    sor = {
        "services": [
            {"id": "services.semantic.EgoMotion", "kind": "event", "period_ms": 50},
            {"id": "services.semantic.Trajectory", "kind": "event", "period_ms": 50},
            {"id": "services.semantic.Orphan", "kind": "event", "period_ms": 50},
        ]
    }
    req = {
        "publish_policy": {
            "services": {
                "EgoMotion": {"trigger": "period", "period_ms": 10},
                "Trajectory": {"trigger": "on_change"},
            }
        }
    }
    warnings = apply_publish_policy(sor, req)
    assert warnings == []
    by_id = {s["id"]: s for s in sor["services"]}
    ego = by_id["services.semantic.EgoMotion"]
    assert ego["trigger"] == "period"
    assert ego["period_ms"] == 10
    assert "expect_fps" not in ego
    traj = by_id["services.semantic.Trajectory"]
    assert traj["trigger"] == "on_change"
    assert "period_ms" not in traj
    orphan = by_id["services.semantic.Orphan"]
    assert orphan["trigger"] == "unspecified"
    assert "period_ms" not in orphan


def test_unknown_trigger_not_migrated() -> None:
    sor = {
        "services": [
            {"id": "services.semantic.Perception_MESSAGE_Out_St", "kind": "event"},
        ]
    }
    req = {
        "frame_ingest": {"camera_slots": [{"id": "front", "fps": 30}]},
        "publish_policy": {
            "services": {
                "Perception_MESSAGE_Out_St": {
                    "trigger": "on_camera",
                    "expect_fps": 20,
                }
            }
        },
    }
    warnings = apply_publish_policy(sor, req)
    assert any("unknown trigger='on_camera'" in w for w in warnings)
    out = sor["services"][0]
    assert out["trigger"] == "unspecified"
    assert "expect_fps" not in out
    assert "period_ms" not in out


def test_expect_fps_above_camera_warns() -> None:
    sor = {
        "services": [
            {"id": "services.semantic.Perception_MESSAGE_Out_St", "kind": "event"},
        ]
    }
    req = {
        "frame_ingest": {"camera_slots": [{"id": "front", "fps": 20}]},
        "publish_policy": {
            "services": {
                "Perception_MESSAGE_Out_St": {
                    "trigger": "on_change",
                    "expect_fps": 30,
                }
            }
        },
    }
    warnings = apply_publish_policy(sor, req)
    assert any("expect_fps=30 > camera fps=20" in w for w in warnings)


def test_camera_fps_ceiling() -> None:
    assert camera_fps_ceiling({}) == 0
    assert (
        camera_fps_ceiling(
            {"frame_ingest": {"camera_slots": [{"id": "front", "fps": 30}]}}
        )
        == 30
    )
    assert (
        camera_fps_ceiling(
            {
                "frame_ingest": {
                    "camera_slots": [
                        {"id": "front", "fps": 30},
                        {"id": "rear", "fps": 20},
                    ]
                }
            }
        )
        == 20
    )


def test_emit_hpp(tmp_path) -> None:
    req = {
        "publish_policy": {
            "services": {
                "EgoMotion": {"trigger": "period", "period_ms": 10},
                "Perception_MESSAGE_Out_St": {
                    "trigger": "on_change",
                    "expect_fps": 20,
                },
            },
            "channels": {"fake_perc": {"trigger": "on_change"}},
        }
    }
    out = tmp_path / "publish_policy.hpp"
    emit_publish_policy_hpp(req, out)
    text = out.read_text(encoding="utf-8")
    assert "gf_gen::publish_policy" in text
    assert "expect_fps" in text
    assert "EgoMotion" in text
    assert "10u" in text
    assert "20u" in text
    assert "on_change" in text
    assert "on_camera" not in text
    assert "fake_perc" in text
