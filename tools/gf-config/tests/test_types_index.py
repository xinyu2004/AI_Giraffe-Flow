"""lookup_type_fields is inspect-only and indexed (no SOR, no per-call yaml)."""

from __future__ import annotations

from pathlib import Path

from gf_config.core import ProjectSession


def _sess(types_yaml: Path | None) -> ProjectSession:
    s = object.__new__(ProjectSession)
    s.paths = type("P", (), {"types_yaml": types_yaml})()
    s._types_by_leaf = None
    s._types_mtime = None
    return s


def test_lookup_empty_without_types_yaml() -> None:
    s = _sess(None)
    assert s.lookup_type_fields("EgoMotion") == []
    assert s.lookup_type_fields("gf.channel.front") == []


def test_lookup_indexes_leaf_and_skips_channel(tmp_path: Path) -> None:
    p = tmp_path / "types.yaml"
    p.write_text(
        "schema_version: '0.1'\n"
        "types:\n"
        "- id: types.EgoMotion\n"
        "  kind: struct\n"
        "  fields:\n"
        "  - name: speed_mps\n"
        "    type: float32\n",
        encoding="utf-8",
    )
    s = _sess(p)
    fields = s.lookup_type_fields("services.semantic.EgoMotion")
    assert fields[0]["name"] == "speed_mps"
    assert s.lookup_type_fields("EgoMotion")[0]["name"] == "speed_mps"
    assert s._types_by_leaf is not None
    assert "EgoMotion" in s._types_by_leaf
    assert s.lookup_type_fields("gf.channel.front") == []
    # second hit uses cache (mtime unchanged)
    s._types_by_leaf["EgoMotion"] = [{"name": "cached", "type": "uint8"}]
    assert s.lookup_type_fields("EgoMotion")[0]["name"] == "cached"
