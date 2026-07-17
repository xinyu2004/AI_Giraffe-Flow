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


def test_parse_fcm_fat_ports(repo_root: Path) -> None:
    from gf_codegen.compose.parse_hpp import is_fat_port_name

    hpp = repo_root / "projects/oem_a/afc_with_uss/interfaces/fcm_perception/io_ports.hpp"
    structs = parse_hpp_file(hpp)
    names = {s["name"] for s in structs}
    assert "Perception_In_St" in names
    assert "Perception_MESSAGE_Out_St" in names
    assert is_fat_port_name("Perception_MESSAGE_Out_St")
    assert not is_fat_port_name("Dyn_OBJ_Item_St")


def test_parse_typedef_struct(tmp_path: Path) -> None:
    p = tmp_path / "t.h"
    p.write_text(
        "typedef struct { uint8_demo a; float32_demo b; } IPC_CanInfo_20ms_St;\n",
        encoding="utf-8",
    )
    structs = parse_hpp_file(p)
    assert structs[0]["name"] == "IPC_CanInfo_20ms_St"
    assert structs[0]["fields"][0]["type"] == "uint8"
