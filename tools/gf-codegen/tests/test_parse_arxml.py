from __future__ import annotations

from pathlib import Path

from gf_codegen.compose.parse_arxml import parse_arxml_file, to_wiring_fragment


def test_parse_demo_arxml(repo_root: Path) -> None:
    path = repo_root / "schemas/examples/oem/demo_faracon_subset.arxml"
    parsed = parse_arxml_file(path)
    assert "EgoMotion" in parsed["interfaces"]
    assert "UssZones" in parsed["interfaces"]
    assert "EgoMotion" in parsed["data_types"]
    assert "VehicleSpeed" in parsed["data_types"]
    assert "EgoMotion" in parsed["candidates"]
    frag = to_wiring_fragment(parsed)
    assert frag["imports_meta"]["sources"][0]["kind"] == "arxml_subset"
