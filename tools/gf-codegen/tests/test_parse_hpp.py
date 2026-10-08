from __future__ import annotations

from pathlib import Path

from gf_codegen.compose.parse_hpp import (
    is_fat_port_name,
    parse_hpp_file,
    structs_to_sor_types,
)


def test_parse_uss(tmp_path: Path) -> None:
    hpp = tmp_path / "uss.hpp"
    hpp.write_text(
        "struct UssZoneSample { float dist_m; };\n"
        "struct UssZones { UssZoneSample zones[6]; };\n",
        encoding="utf-8",
    )
    structs = parse_hpp_file(hpp)
    names = {s["name"] for s in structs}
    assert "UssZones" in names
    assert "UssZoneSample" in names
    types = structs_to_sor_types(structs)
    uz = next(t for t in types if t["id"] == "types.UssZones")
    zone_field = next(f for f in uz["fields"] if f["name"] == "zones")
    assert zone_field["type"] == "types.UssZoneSample"
    assert zone_field["array_size"] == 6


def test_parse_front(tmp_path: Path) -> None:
    hpp = tmp_path / "front.hpp"
    hpp.write_text("struct FrontObjectList { uint8_t count; };\n", encoding="utf-8")
    structs = parse_hpp_file(hpp)
    names = {s["name"] for s in structs}
    assert "FrontObjectList" in names


def test_parse_fcm_fat_ports(tmp_path: Path) -> None:
    ports = tmp_path / "io_ports.hpp"
    ports.write_text(
        "struct Perception_In_St { uint64_t timestamp_ns; };\n"
        "struct Perception_MESSAGE_Out_St { uint8_t n; };\n"
        "struct Dyn_OBJ_Item_St { uint8_t id; };\n",
        encoding="utf-8",
    )
    structs = parse_hpp_file(ports)
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


def test_parse_gold_out_macros(tmp_path: Path) -> None:
    hpp = tmp_path / "gold.h"
    hpp.write_text(
        "#define OBJ_NUM 13\n"
        "typedef struct {\n"
        "  uint8_demo m_OBJ_Object_Class;\n"
        "} Dyn_OBJ_Item_St;\n"
        "typedef struct {\n"
        "  Dyn_OBJ_Item_St m_Obj_item[OBJ_NUM];\n"
        "} Perception_Dyn_OBJ_Out_St;\n"
        "typedef struct {\n"
        "  Perception_Dyn_OBJ_Out_St dyn;\n"
        "} Perception_MESSAGE_Out_St;\n",
        encoding="utf-8",
    )
    structs = parse_hpp_file(hpp)
    names = {s["name"] for s in structs}
    assert "Perception_MESSAGE_Out_St" in names
    assert "Dyn_OBJ_Item_St" in names
    dyn = next(s for s in structs if s["name"] == "Perception_Dyn_OBJ_Out_St")
    item = next(f for f in dyn["fields"] if f["name"] == "m_Obj_item")
    assert item["array_size"] == 13
    types = structs_to_sor_types(structs)
    item_t = next(t for t in types if t["id"] == "types.Dyn_OBJ_Item_St")
    cls = next(f for f in item_t["fields"] if f["name"] == "m_OBJ_Object_Class")
    assert cls["type"] == "uint8"
