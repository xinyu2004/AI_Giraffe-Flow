"""Tests for gf-codegen generate (types + Proxy/Skeleton)."""

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

    types = out / "include/gf_gen/types"
    assert (types / "ego_motion.hpp").is_file()
    assert (types / "trajectory.hpp").is_file()
    ego = (types / "ego_motion.hpp").read_text(encoding="utf-8")
    assert "struct EgoMotion" in ego or "EgoMotion" in ego

    skel = out / "include/gf_gen/skeleton/ego_motion_skeleton.hpp"
    proxy = out / "include/gf_gen/proxy/ego_motion_proxy.hpp"
    assert skel.is_file()
    assert proxy.is_file()
    skel_txt = skel.read_text(encoding="utf-8")
    assert "class EgoMotionSkeleton" in skel_txt
    assert "EventPublisher" in skel_txt
    proxy_txt = proxy.read_text(encoding="utf-8")
    assert "class EgoMotionProxy" in proxy_txt
    assert "EventSubscriber" in proxy_txt


def test_generate_adc_proxy_skeleton(repo_root: Path, tmp_path: Path) -> None:
    project = repo_root / "projects/adc/giraffe.yaml"
    assert compose_project(project, repo_root=repo_root) == 0
    sor = repo_root / "projects/adc/gf.sor.json"
    out = tmp_path / "generated"
    assert generate(sor, out) == 0

    types = out / "include/gf_gen/types"
    assert (types / "surround_world.hpp").is_file()
    assert (types / "parking_trajectory.hpp").is_file()
    assert (types / "ego_motion.hpp").is_file()

    assert (out / "include/gf_gen/skeleton/surround_world_skeleton.hpp").is_file()
    assert (out / "include/gf_gen/proxy/surround_world_proxy.hpp").is_file()
    assert (out / "include/gf_gen/proxy/parking_trajectory_proxy.hpp").is_file()
    assert (out / "include/gf_gen/skeleton/parking_trajectory_skeleton.hpp").is_file()
