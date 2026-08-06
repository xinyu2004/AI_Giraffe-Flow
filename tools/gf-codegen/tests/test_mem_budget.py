"""BL-MEM-BOUND estimate formulas (reviewable)."""

from __future__ import annotations

from gf_codegen.compose.mem_budget import (
    C_DEBOUNCE_ENTRY,
    C_DLT_CTX,
    C_EVENT_RECORD,
    C_PER_KEY_OH,
    estimate_mem_budget,
    format_estimate_text,
    fmt_bytes,
)


def test_estimate_defaults_match_formulas() -> None:
    plat = {
        "log": {
            "sinks": ["console", "file", "dlt"],
            "file_max_bytes": 1_048_576,
            "contexts": [{"id": "a"}, {"id": "b"}],
        },
        "collector": {
            "local": {
                "enabled": True,
                "max_entries": 256,
                "debounce_max_keys": 64,
                "store_max_bytes": 1_048_576,
            }
        },
        "diag": {
            "doip": {"rx_max_bytes": 65536},
            "ota_transfer": {"max_block_length": 1024},
        },
        "bounds": {
            "dlt": {"max_contexts": 64},
            "com": {
                "queue_depth": 16,
                "max_topic_keys": 64,
                "avg_payload_bytes": 256,
            },
            "per": {"max_keys": 1024, "max_value_bytes": 65536},
            "diag": {"dids": {"max_entries": 256, "max_payload": 4096}},
            "budget": {"ram_bytes": 0, "disk_bytes": 0},
        },
    }
    est = estimate_mem_budget(plat)
    assert est["errors"] == []
    by = {ln["name"]: ln["bytes"] for ln in est["lines"]}
    assert by["collector_ring"] == 256 * C_EVENT_RECORD
    assert by["collector_debounce"] == 64 * C_DEBOUNCE_ENTRY
    assert by["com_loopback"] == 64 * 16 * 256
    assert by["diag_rx"] == 65536
    assert by["diag_dids"] == 256 * 4096
    assert by["diag_ota_block"] == 1024
    assert by["per_kv"] == 1024 * (C_PER_KEY_OH + 65536)
    assert by["dlt_contexts"] == 64 * C_DLT_CTX
    assert by["log_files"] == 1_048_576 * 2
    assert by["collector_store"] == 1_048_576 * 2
    assert est["total_ram_bytes"] == sum(
        by[k]
        for k in (
            "collector_ring",
            "collector_debounce",
            "com_loopback",
            "diag_rx",
            "diag_dids",
            "diag_ota_block",
            "per_kv",
            "dlt_contexts",
        )
    )
    text = format_estimate_text(est)
    assert "collector_ring" in text
    assert "←" in text
    assert "MiB" in text
    assert "MiB" in fmt_bytes(1_048_576)
    assert fmt_bytes(1_048_576) == "1048576 B (1.00 MiB)"


def test_contexts_over_dlt_max_is_error() -> None:
    plat = {
        "log": {"contexts": [{"id": f"c{i}"} for i in range(10)]},
        "bounds": {"dlt": {"max_contexts": 4}},
    }
    est = estimate_mem_budget(plat)
    assert any("max_contexts" in e for e in est["errors"])


def test_budget_warn() -> None:
    plat = {
        "collector": {"local": {"max_entries": 256, "enabled": True}},
        "bounds": {"budget": {"ram_bytes": 100}},
    }
    est = estimate_mem_budget(plat)
    assert any("total_ram" in w for w in est["warnings"])


def test_roudi_payload_formula() -> None:
    from gf_codegen.compose.mem_budget import (
        C_CHUNK_HDR,
        approx_roudi_mgmt_bytes,
    )

    plat = {
        "bounds": {
            "iceoryx": {
                "mgmt": {"max_publishers": 8},
                "mempools": [
                    {"size": 256, "count": 10},
                    {"size": 1024, "count": 2},
                ],
            }
        }
    }
    est = estimate_mem_budget(plat, req={"bindings": ["iceoryx"]})
    by = {ln["name"]: ln["bytes"] for ln in est["lines"]}
    assert by["roudi_payload"] == (256 + C_CHUNK_HDR) * 10 + (1024 + C_CHUNK_HDR) * 2
    assert est["roudi_mgmt_status"] == "approx"
    assert "roudi_mgmt" in by
    approx_b, _ = approx_roudi_mgmt_bytes(est["iceoryx_mgmt"])
    assert by["roudi_mgmt"] == approx_b
    assert by["roudi_mgmt"] > 0
    assert any("approximate" in w for w in est["warnings"])


def test_roudi_mgmt_model_matches_sil_default() -> None:
    from gf_codegen.compose.emit_iox import DEFAULT_MGMT
    from gf_codegen.compose.mem_budget import IOX_MGMT_REF_BYTES, model_roudi_mgmt_bytes

    # SIL-measured DEF within ~100 B of fit (rounding).
    assert abs(model_roudi_mgmt_bytes(DEFAULT_MGMT) - IOX_MGMT_REF_BYTES) < 100


def test_roudi_mgmt_model_tracks_publisher_doubling() -> None:
    from gf_codegen.compose.emit_iox import DEFAULT_MGMT
    from gf_codegen.compose.mem_budget import model_roudi_mgmt_bytes

    # Measured: P 32→64 → 22980216
    m = {**DEFAULT_MGMT, "max_publishers": 64}
    assert abs(model_roudi_mgmt_bytes(m) - 22_980_216) < 100


def test_roudi_mgmt_measured_when_report_matches(tmp_path) -> None:
    import json

    from gf_codegen.compose.emit_iox import DEFAULT_MGMT
    from gf_codegen.compose.mem_budget import IOX_MGMT_REF_BYTES

    report = {
        "schema_version": "0.2",
        "mgmt_bytes": IOX_MGMT_REF_BYTES,
        "mgmt": dict(DEFAULT_MGMT),
    }
    path = tmp_path / "iox_shm_report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    plat = {"bounds": {"iceoryx": {"mgmt": dict(DEFAULT_MGMT), "mempools": [{"size": 256, "count": 1}]}}}
    est = estimate_mem_budget(plat, req={"bindings": ["iceoryx"]}, shm_report_path=path)
    by = {ln["name"]: ln["bytes"] for ln in est["lines"]}
    assert est["roudi_mgmt_status"] == "measured"
    assert by["roudi_mgmt"] == IOX_MGMT_REF_BYTES


def test_roudi_mgmt_approx_scales_when_knobs_change(tmp_path) -> None:
    import json

    from gf_codegen.compose.emit_iox import DEFAULT_MGMT
    from gf_codegen.compose.mem_budget import IOX_MGMT_REF_BYTES, approx_roudi_mgmt_bytes

    report = {
        "mgmt_bytes": IOX_MGMT_REF_BYTES,
        "mgmt": dict(DEFAULT_MGMT),
    }
    path = tmp_path / "iox_shm_report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    changed = {**DEFAULT_MGMT, "max_publishers": 64}
    plat = {"bounds": {"iceoryx": {"mgmt": changed, "mempools": [{"size": 256, "count": 1}]}}}
    est = estimate_mem_budget(plat, req={"bindings": ["iceoryx"]}, shm_report_path=path)
    by = {ln["name"]: ln["bytes"] for ln in est["lines"]}
    expect, _ = approx_roudi_mgmt_bytes(
        changed, calibrate_mgmt=DEFAULT_MGMT, calibrate_bytes=IOX_MGMT_REF_BYTES
    )
    assert est["roudi_mgmt_status"] == "approx"
    assert by["roudi_mgmt"] == expect
    assert by["roudi_mgmt"] != IOX_MGMT_REF_BYTES
