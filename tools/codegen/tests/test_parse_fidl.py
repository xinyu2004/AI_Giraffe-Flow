from __future__ import annotations

from pathlib import Path

from gf_codegen.compose.parse_fidl import fidl_structs_to_sor_types, parse_fidl_file


def test_parse_sample_vehicle_status(repo_root: Path) -> None:
    fidl = repo_root / "projects/oem_a/afc_with_uss/interfaces/demo_fidl/VehicleStatus.fidl"
    parsed = parse_fidl_file(fidl)
    assert parsed["package"] == "oem_a.demo"
    assert {i["name"] for i in parsed["interfaces"]} == {"VehicleStatus"}
    assert "VehiclePose" in {s["name"] for s in parsed["structs"]}
    assert "SpeedChanged" in parsed["broadcasts"]
    assert "getPose" in parsed["methods"]
    assert "VehiclePose" in parsed["candidates"]
    assert "SpeedChanged" in parsed["candidates"]

    types = fidl_structs_to_sor_types(parsed["structs"])
    pose = next(t for t in types if t["id"] == "types.VehiclePose")
    names = {f["name"]: f["type"] for f in pose["fields"]}
    assert names["x"] == "float32"
    assert names["y"] == "float32"
    assert names["yaw"] == "float32"


def test_candidates_order_stable(tmp_path: Path) -> None:
    p = tmp_path / "t.fidl"
    p.write_text(
        """
package demo
interface Foo {
  method bar { }
  broadcast Baz { out { Int32 v } }
}
typeCollection T {
  struct Pos { Int32 x }
}
""",
        encoding="utf-8",
    )
    c = parse_fidl_file(p)["candidates"]
    assert c[0] == "Pos"
    assert "Baz" in c
    assert "bar" in c
    assert "Foo" in c
