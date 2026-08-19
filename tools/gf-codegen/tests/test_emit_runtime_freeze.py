"""runtime freeze headers from platform_manifest."""

from __future__ import annotations

from pathlib import Path

from gf_codegen.compose.emit_runtime_freeze import emit_runtime_freeze


def test_emit_runtime_freeze_defaults(tmp_path: Path) -> None:
    meta = emit_runtime_freeze({}, tmp_path)
    coll = Path(meta["collector"]).read_text(encoding="utf-8")
    assert 'kForward = "local_store"' in coll
    assert "kSources[]" in coll
    bounds = Path(meta["bounds"]).read_text(encoding="utf-8")
    assert "kComQueueDepth = 16u" in bounds
    assert "kDidMaxEntries = 256u" in bounds
    ucm = Path(meta["ucm"]).read_text(encoding="utf-8")
    assert "kEnabled = true" in ucm
    assert 'kFunctionGroup = "MachineFG"' in ucm


def test_emit_runtime_freeze_full(tmp_path: Path) -> None:
    manifest = {
        "collector": {
            "forward": "both",
            "sources": ["phm", "ucm"],
            "local": {"enabled": True, "max_entries": 128, "debounce_max_keys": 32,
                      "store_max_bytes": 4096},
            "dtc_map": [
                {"event": "AliveMissed", "dtc": 0xC01234, "debounce_count": 2,
                 "fdc_threshold": 3, "aging_cycles": 10},
            ],
            "freeze_dids": [0xF191],
        },
        "bounds": {
            "com": {"queue_depth": 8, "max_topic_keys": 16},
            "per": {"max_keys": 64, "max_value_bytes": 512},
            "dlt": {"max_contexts": 16},
            "diag": {"rx_max_bytes": 1024, "dids": {"max_entries": 32, "max_payload": 64}},
        },
        "ucm": {
            "enabled": False,
            "allow_rollback": False,
            "function_group": "UpdateFG",
            "package_source": "sil://x",
        },
        "diag": {
            "dids": [{"id": 0xF190, "name": "VIN"}],
        },
    }
    meta = emit_runtime_freeze(manifest, tmp_path)
    coll = Path(meta["collector"]).read_text(encoding="utf-8")
    assert 'kForward = "both"' in coll
    assert '"phm"' in coll and '"ucm"' in coll
    assert "AliveMissed" in coll and "0xc01234" in coll.lower()
    assert "0xf191" in coll.lower()
    bounds = Path(meta["bounds"]).read_text(encoding="utf-8")
    assert "kComQueueDepth = 8u" in bounds
    assert "kDiagRxMaxBytes = 1024u" in bounds
    ucm = Path(meta["ucm"]).read_text(encoding="utf-8")
    assert "kEnabled = false" in ucm
    assert 'kFunctionGroup = "UpdateFG"' in ucm
    seed = Path(meta["diag_seed"]).read_text(encoding="utf-8")
    assert "0xf190" in seed.lower() and "VIN" in seed
