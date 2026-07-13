"""Tests for gf-codegen generate (types + Proxy/Skeleton)."""

from __future__ import annotations

from pathlib import Path

from gf_codegen.compose.pipeline import compose_project
from gf_codegen.generate_cmd import generate


def test_generate_afc_with_uss_proxy_skeleton(repo_root: Path, tmp_path: Path) -> None:
    project = repo_root / "projects/oem_a/afc_with_uss/project.yaml"
    assert compose_project(project, repo_root=repo_root) == 0
    sor = repo_root / "projects/oem_a/afc_with_uss/gf.sor.json"
    out = tmp_path / "generated"
    assert generate(sor, out) == 0

    types = out / "include/gf_gen/types"
    assert (types / "uss_zones.hpp").is_file()
    assert (types / "uss_zone_sample.hpp").is_file()
    uss = (types / "uss_zones.hpp").read_text(encoding="utf-8")
    assert "UssZoneSample zones[6]" in uss
    assert '#include "gf_gen/types/uss_zone_sample.hpp"' in uss

    skel = out / "include/gf_gen/skeleton/uss_zones_skeleton.hpp"
    proxy = out / "include/gf_gen/proxy/uss_zones_proxy.hpp"
    assert skel.is_file()
    assert proxy.is_file()
    skel_txt = skel.read_text(encoding="utf-8")
    assert "class UssZonesSkeleton" in skel_txt
    assert "EventPublisher" in skel_txt
    assert "semantic.UssZones" in skel_txt
    proxy_txt = proxy.read_text(encoding="utf-8")
    assert "class UssZonesProxy" in proxy_txt
    assert "EventSubscriber" in proxy_txt


def test_generate_adc_full_proxy_skeleton(repo_root: Path, tmp_path: Path) -> None:
    project = repo_root / "projects/oem_b/adc_full/project.yaml"
    assert compose_project(project, repo_root=repo_root) == 0
    sor = repo_root / "projects/oem_b/adc_full/gf.sor.json"
    out = tmp_path / "generated"
    assert generate(sor, out) == 0

    types = out / "include/gf_gen/types"
    assert (types / "parking_world.hpp").is_file()
    assert (types / "surround_world.hpp").is_file()
    assert (types / "ego_motion_extended.hpp").is_file()

    assert (out / "include/gf_gen/skeleton/parking_world_skeleton.hpp").is_file()
    assert (out / "include/gf_gen/proxy/parking_world_proxy.hpp").is_file()
    assert (out / "include/gf_gen/proxy/ego_motion_extended_proxy.hpp").is_file()
    assert (out / "include/gf_gen/skeleton/actuator_command_skeleton.hpp").is_file()
