from __future__ import annotations

from pathlib import Path

from gf_codegen.emit_idl import emit_idl_from_sor, write_idl


def test_emit_idl_structs(tmp_path: Path) -> None:
    sor = {
        "types": [
            {
                "id": "types.EgoMotion",
                "kind": "struct",
                "fields": [
                    {"name": "timestamp_ns", "type": "uint64"},
                    {"name": "speed_mps", "type": "float32"},
                    {"name": "zones", "type": "uint8", "array_size": 6},
                ],
            },
            {
                "id": "types.Nested",
                "kind": "struct",
                "fields": [{"name": "ego", "type": "types.EgoMotion"}],
            },
        ]
    }
    text = emit_idl_from_sor(sor)
    assert "module gf_types {" in text
    assert "struct EgoMotion {" in text
    assert "uint64 timestamp_ns;" in text
    assert "float speed_mps;" in text
    assert "uint8 zones[6];" in text
    assert "EgoMotion ego;" in text

    sor_path = tmp_path / "t.sor.json"
    import json

    sor_path.write_text(json.dumps(sor), encoding="utf-8")
    out = write_idl(sor_path, tmp_path / "idl")
    assert out.is_file()
    assert "EgoMotion" in out.read_text(encoding="utf-8")
