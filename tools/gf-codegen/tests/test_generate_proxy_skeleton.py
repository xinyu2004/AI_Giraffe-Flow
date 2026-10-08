"""Tests for gf-codegen generate (one service header = structs + Proxy/Skeleton)."""

from __future__ import annotations

from pathlib import Path

from gf_codegen.compose.pipeline import compose_project
from gf_codegen.generate_cmd import generate


def test_generate_afc_proxy_skeleton(repo_root: Path, tmp_path: Path) -> None:
    project = repo_root / "projects/afc/giraffe.yaml"
    assert compose_project(project, repo_root=repo_root) == 0
    sor = repo_root / "projects/afc/gf.sor.json"
    out = tmp_path / "generated"
    assert generate(sor, out) == 0

    gf = out / "include/gf_gen"
    ego = gf / "ego_motion.hpp"
    assert ego.is_file()
    ego_txt = ego.read_text(encoding="utf-8")
    assert "struct EgoMotion" in ego_txt
    assert "class EgoMotionSkeleton" in ego_txt
    assert "EventPublisher" in ego_txt
    assert "class EgoMotionProxy" in ego_txt
    assert "EventSubscriber" in ego_txt
    assert (gf / "driving_trajectory.hpp").is_file()
    assert not (gf / "types").exists()
    assert not (gf / "proxy").exists()
    assert not (gf / "skeleton").exists()
    assert not (gf / "ipc__can_info_10ms__st.hpp").is_file()
    assert not (gf / "perception_la__out__st.hpp").is_file()

    fcm = (gf / "perception_message__out__st.hpp").read_text(encoding="utf-8")
    assert "struct Perception_LA_Out_St" in fcm
    assert "struct Perception_HLB_Out_St" in fcm
    assert "class Perception_MESSAGE_Out_StSkeleton" in fcm
    assert "class Perception_MESSAGE_Out_StProxy" in fcm


def test_generate_adc_proxy_skeleton(repo_root: Path, tmp_path: Path) -> None:
    project = repo_root / "projects/adc/giraffe.yaml"
    assert compose_project(project, repo_root=repo_root) == 0
    sor = repo_root / "projects/adc/gf.sor.json"
    out = tmp_path / "generated"
    assert generate(sor, out) == 0

    gf = out / "include/gf_gen"
    sw = (gf / "surround_world.hpp").read_text(encoding="utf-8")
    assert "struct DetectedParkingSlot" in sw
    assert "struct SurroundWorld" in sw
    assert "class SurroundWorldSkeleton" in sw
    assert "class SurroundWorldProxy" in sw
    park = (gf / "parking_trajectory.hpp").read_text(encoding="utf-8")
    assert "class ParkingTrajectorySkeleton" in park
    assert "class ParkingTrajectoryProxy" in park
    assert (gf / "ego_motion.hpp").is_file()
    assert (gf / "apa_status.hpp").is_file()
    assert not (gf / "types").exists()
    assert not (gf / "proxy").exists()
    assert not (gf / "skeleton").exists()
    assert not (gf / "perception_hlb__out__st.hpp").is_file()
