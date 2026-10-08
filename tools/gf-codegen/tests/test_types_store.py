from __future__ import annotations

from pathlib import Path

from gf_codegen.compose.types_store import (
    ingest_hpp_into_types,
    load_types_yaml,
    merge_types_into_sor,
)


def test_ingest_hpp_writes_types_yaml(tmp_path: Path) -> None:
    hpp = tmp_path / "vendor.h"
    hpp.write_text(
        "struct EgoMotion { float speed_mps; };\n"
        "struct ParkingSlot { float fParkingSlot_P0X; };\n",
        encoding="utf-8",
    )
    incoming = ingest_hpp_into_types(tmp_path, hpp)
    ids = {t["id"] for t in incoming}
    assert "types.EgoMotion" in ids
    stored = load_types_yaml(tmp_path / "cfg" / "types.yaml")
    assert {t["id"] for t in stored} == ids
    ego = next(t for t in stored if t["id"] == "types.EgoMotion")
    assert ego["fields"][0]["name"] == "speed_mps"


def test_merge_types_into_sor_overwrites() -> None:
    sor = {"types": [{"id": "types.EgoMotion", "kind": "struct", "fields": []}]}
    merge_types_into_sor(
        sor,
        [
            {
                "id": "types.EgoMotion",
                "kind": "struct",
                "fields": [{"name": "speed_mps", "type": "float32"}],
            }
        ],
    )
    ego = next(t for t in sor["types"] if t["id"] == "types.EgoMotion")
    assert ego["fields"][0]["name"] == "speed_mps"
