from __future__ import annotations

from pathlib import Path

from gf_codegen.compose.parse_hpp import parse_hpp_file, structs_to_sor_types


def test_parse_uss(repo_root: Path) -> None:
    hpp = repo_root / "projects/oem_a/afc_with_uss/interfaces/uss_sensing/io_types.hpp"
    structs = parse_hpp_file(hpp)
    names = {s["name"] for s in structs}
    assert "UssZones" in names
    assert "UssZoneSample" in names
    types = structs_to_sor_types(structs)
    uz = next(t for t in types if t["id"] == "types.UssZones")
    zone_field = next(f for f in uz["fields"] if f["name"] == "zones")
    assert zone_field["type"] == "types.UssZoneSample"
    assert zone_field["array_size"] == 6


def test_parse_front(repo_root: Path) -> None:
    hpp = repo_root / "projects/oem_a/afc_with_uss/interfaces/perception_front/io_types.hpp"
    structs = parse_hpp_file(hpp)
    names = {s["name"] for s in structs}
    assert "FrontObjectList" in names
    assert "EgoMotion" in names
