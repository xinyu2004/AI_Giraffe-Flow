"""BL-MEM-BOUND / BL-MEM-ROUDI — static upper-bound estimate for platform memory.

FORMULAS (reviewable; conservative upper bounds, not measured RSS)
=================================================================

Constants (bytes / entry) — keep in sync with middleware when structs change:

  C_EVENT_RECORD   = 256   # EventRecord hot path: strings + meta (padded)
  C_DEBOUNCE_ENTRY = 48    # event_id key + hits + first_ns
  C_DLT_CTX        = 64    # DltContext handle + id map slot
  C_PER_KEY_OH     = 32    # key string overhead in RAM map
  C_CHUNK_HDR      = 64    # iceoryx ChunkHeader overhead on each mempool chunk

Disk: file sinks keep path + path.1 (×2). Same for collector NDJSON store.

RAM (process-local)
-------------------
  collector_ring   = max_entries × C_EVENT_RECORD
  collector_deb    = debounce_max_keys × C_DEBOUNCE_ENTRY
  com_queues       = max_topic_keys × queue_depth × avg_payload_bytes   # LoopbackBus only
  diag_rx          = rx_max_bytes
  diag_dids        = dids.max_entries × dids.max_payload
  per_kv           = max_keys × (C_PER_KEY_OH + max_value_bytes)
  dlt_ctx          = dlt.max_contexts × C_DLT_CTX
  ota_block        = ota_transfer.max_block_length

  total_ram = sum(above)

DISK
----
  log_files        = file_max_bytes × 2   (if file sink enabled; else 0)
  collector_store  = store_max_bytes × 2  (if local store enabled; else 0)

  total_disk = sum(above)

SHM — iceoryx / RouDi (BL-MEM-ROUDI; when req.bindings includes iceoryx)
------------------------------------------------------------------------
  roudi_payload = Σ_i (mempool[i].size + C_CHUNK_HDR) × mempool[i].count
                (same numbers as generated/iox_roudi.toml)

  roudi_mgmt    = measured bytes from generated/iox_shm_report.json after
                RouDi/build (iceoryx_mgmt has no closed-form formula).
                Until measured: status pending_measure, bytes=0 in sum.
                Config intent is bounds.iceoryx.mgmt.* → CMake IOX_MAX_*
                (change requires reconfigure + rebuild iceoryx).

  total_shm = roudi_payload + roudi_mgmt(measured)

Notes
-----
- GMT host-side queues are **not** included (not on board).
- LoopbackBus estimate is orthogonal to RouDi SHM.

Checks
------
- error: len(log.contexts) > dlt.max_contexts
- warn:  total_ram > budget.ram_bytes (if budget > 0)
- warn:  total_disk > budget.disk_bytes (if budget > 0)
- warn:  total_shm > iceoryx.budget_shm_bytes (if > 0 and mgmt measured or payload alone)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gf_codegen.compose.emit_iox import DEFAULT_MEMPOOLS, DEFAULT_MGMT, extract_iox, iceoryx_enabled

# --- formula constants (bytes) — change only with middleware review ---
C_EVENT_RECORD = 256
C_DEBOUNCE_ENTRY = 48
C_DLT_CTX = 64
C_PER_KEY_OH = 32
C_CHUNK_HDR = 64

DEFAULTS: dict[str, int] = {
    "max_entries": 256,
    "debounce_max_keys": 64,
    "store_max_bytes": 1_048_576,
    "file_max_bytes": 1_048_576,
    "dlt_max_contexts": 64,
    "com_queue_depth": 16,
    "com_max_topic_keys": 64,
    "com_avg_payload_bytes": 256,
    "per_max_keys": 1024,
    "per_max_value_bytes": 65_536,
    "diag_rx_max_bytes": 65_536,
    "dids_max_entries": 256,
    "dids_max_payload": 4096,
    "ota_max_block_length": 1024,
}


def _i(d: dict[str, Any] | None, *keys: str, default: int = 0) -> int:
    cur: Any = d or {}
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    if cur is None:
        return default
    try:
        return int(cur)
    except (TypeError, ValueError):
        return default


def _sinks_include_file(log: dict[str, Any]) -> bool:
    sinks = log.get("sinks") or []
    if isinstance(sinks, list):
        return any(str(s).strip().lower() == "file" for s in sinks)
    return False


def load_iox_shm_report(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def extract_caps(platform: dict[str, Any]) -> dict[str, int]:
    """Flatten caps from platform_manifest / loaded yaml map."""
    log = platform.get("log") or {}
    col = platform.get("collector") or {}
    local = col.get("local") if isinstance(col.get("local"), dict) else {}
    bounds = platform.get("bounds") or {}
    dlt_b = bounds.get("dlt") if isinstance(bounds.get("dlt"), dict) else {}
    com_b = bounds.get("com") if isinstance(bounds.get("com"), dict) else {}
    per_b = bounds.get("per") if isinstance(bounds.get("per"), dict) else {}
    diag_b = bounds.get("diag") if isinstance(bounds.get("diag"), dict) else {}
    dids_b = diag_b.get("dids") if isinstance(diag_b.get("dids"), dict) else {}
    budget = bounds.get("budget") if isinstance(bounds.get("budget"), dict) else {}
    diag = platform.get("diag") or {}
    doip = diag.get("doip") if isinstance(diag.get("doip"), dict) else {}
    ota = diag.get("ota_transfer") if isinstance(diag.get("ota_transfer"), dict) else {}

    return {
        "max_entries": _i(local, "max_entries", default=DEFAULTS["max_entries"]),
        "debounce_max_keys": _i(
            local, "debounce_max_keys", default=DEFAULTS["debounce_max_keys"]
        ),
        "store_max_bytes": _i(local, "store_max_bytes", default=DEFAULTS["store_max_bytes"]),
        "local_enabled": 1 if local.get("enabled", True) else 0,
        "file_max_bytes": _i(log, "file_max_bytes", default=DEFAULTS["file_max_bytes"]),
        "file_sink": 1 if _sinks_include_file(log) else 0,
        "log_contexts": len(log.get("contexts") or [])
        if isinstance(log.get("contexts"), list)
        else 0,
        "dlt_max_contexts": _i(dlt_b, "max_contexts", default=DEFAULTS["dlt_max_contexts"]),
        "com_queue_depth": _i(com_b, "queue_depth", default=DEFAULTS["com_queue_depth"]),
        "com_max_topic_keys": _i(
            com_b, "max_topic_keys", default=DEFAULTS["com_max_topic_keys"]
        ),
        "com_avg_payload_bytes": _i(
            com_b, "avg_payload_bytes", default=DEFAULTS["com_avg_payload_bytes"]
        ),
        "per_max_keys": _i(per_b, "max_keys", default=DEFAULTS["per_max_keys"]),
        "per_max_value_bytes": _i(
            per_b, "max_value_bytes", default=DEFAULTS["per_max_value_bytes"]
        ),
        "diag_rx_max_bytes": _i(
            doip,
            "rx_max_bytes",
            default=_i(diag_b, "rx_max_bytes", default=DEFAULTS["diag_rx_max_bytes"]),
        ),
        "dids_max_entries": _i(dids_b, "max_entries", default=DEFAULTS["dids_max_entries"]),
        "dids_max_payload": _i(dids_b, "max_payload", default=DEFAULTS["dids_max_payload"]),
        "ota_max_block_length": _i(
            ota, "max_block_length", default=DEFAULTS["ota_max_block_length"]
        ),
        "budget_ram_bytes": _i(budget, "ram_bytes", default=0),
        "budget_disk_bytes": _i(budget, "disk_bytes", default=0),
    }


def estimate_mem_budget(
    platform: dict[str, Any],
    *,
    req: dict[str, Any] | None = None,
    shm_report_path: Path | None = None,
) -> dict[str, Any]:
    """Return estimate dict with lines, totals, formulas, errors, warnings."""
    c = extract_caps(platform)
    lines: list[dict[str, Any]] = []

    def add(name: str, formula: str, value: int, *, kind: str) -> None:
        lines.append(
            {
                "name": name,
                "kind": kind,  # ram | disk | shm
                "formula": formula,
                "bytes": int(value),
            }
        )

    ring = c["max_entries"] * C_EVENT_RECORD
    add(
        "collector_ring",
        f"max_entries({c['max_entries']}) × C_EVENT_RECORD({C_EVENT_RECORD})",
        ring,
        kind="ram",
    )
    deb = c["debounce_max_keys"] * C_DEBOUNCE_ENTRY
    add(
        "collector_debounce",
        f"debounce_max_keys({c['debounce_max_keys']}) × C_DEBOUNCE_ENTRY({C_DEBOUNCE_ENTRY})",
        deb,
        kind="ram",
    )
    com = c["com_max_topic_keys"] * c["com_queue_depth"] * c["com_avg_payload_bytes"]
    add(
        "com_loopback",
        f"max_topic_keys({c['com_max_topic_keys']}) × queue_depth({c['com_queue_depth']}) "
        f"× avg_payload_bytes({c['com_avg_payload_bytes']})",
        com,
        kind="ram",
    )
    add(
        "diag_rx",
        f"rx_max_bytes({c['diag_rx_max_bytes']})",
        c["diag_rx_max_bytes"],
        kind="ram",
    )
    dids = c["dids_max_entries"] * c["dids_max_payload"]
    add(
        "diag_dids",
        f"dids.max_entries({c['dids_max_entries']}) × dids.max_payload({c['dids_max_payload']})",
        dids,
        kind="ram",
    )
    add(
        "diag_ota_block",
        f"ota_transfer.max_block_length({c['ota_max_block_length']})",
        c["ota_max_block_length"],
        kind="ram",
    )
    per = c["per_max_keys"] * (C_PER_KEY_OH + c["per_max_value_bytes"])
    add(
        "per_kv",
        f"max_keys({c['per_max_keys']}) × (C_PER_KEY_OH({C_PER_KEY_OH}) "
        f"+ max_value_bytes({c['per_max_value_bytes']}))",
        per,
        kind="ram",
    )
    dlt = c["dlt_max_contexts"] * C_DLT_CTX
    add(
        "dlt_contexts",
        f"dlt.max_contexts({c['dlt_max_contexts']}) × C_DLT_CTX({C_DLT_CTX})",
        dlt,
        kind="ram",
    )

    log_disk = (c["file_max_bytes"] * 2) if c["file_sink"] else 0
    add(
        "log_files",
        f"file_sink={bool(c['file_sink'])}: file_max_bytes({c['file_max_bytes']}) × 2",
        log_disk,
        kind="disk",
    )
    store_disk = (c["store_max_bytes"] * 2) if c["local_enabled"] else 0
    add(
        "collector_store",
        f"local.enabled={bool(c['local_enabled'])}: store_max_bytes({c['store_max_bytes']}) × 2",
        store_disk,
        kind="disk",
    )

    iox_mgmt: dict[str, int] = dict(DEFAULT_MGMT)
    iox_pools: list[dict[str, int]] = [dict(x) for x in DEFAULT_MEMPOOLS]
    budget_shm = 0
    iox_on = iceoryx_enabled(req) if req is not None else bool(
        isinstance((platform.get("bounds") or {}).get("iceoryx"), dict)
    )
    # When req omitted but bounds.iceoryx present (gf-config live estimate), still show SHM
    bounds = platform.get("bounds") if isinstance(platform.get("bounds"), dict) else {}
    if isinstance(bounds.get("iceoryx"), dict):
        iox_mgmt, iox_pools, budget_shm = extract_iox(bounds)
        if req is None:
            iox_on = True
    elif iox_on:
        iox_mgmt, iox_pools, budget_shm = extract_iox(bounds)

    mgmt_status = "n/a"
    mgmt_bytes = 0
    if iox_on:
        parts = [
            f"(size({p['size']})+C_CHUNK_HDR({C_CHUNK_HDR}))×count({p['count']})"
            for p in iox_pools
        ]
        payload = sum((p["size"] + C_CHUNK_HDR) * p["count"] for p in iox_pools)
        add(
            "roudi_payload",
            " + ".join(parts) if parts else "0",
            payload,
            kind="shm",
        )
        report = load_iox_shm_report(shm_report_path)
        if report and report.get("mgmt_bytes") is not None:
            try:
                mgmt_bytes = int(report["mgmt_bytes"])
                mgmt_status = "measured"
            except (TypeError, ValueError):
                mgmt_status = "pending_measure"
                mgmt_bytes = 0
        else:
            mgmt_status = "pending_measure"
            mgmt_bytes = 0
        iox_list = ", ".join(f"{k}={v}" for k, v in sorted(iox_mgmt.items()))
        add(
            "roudi_mgmt",
            f"status={mgmt_status}; IOX intent: {iox_list}"
            + (f"; measured={mgmt_bytes} B" if mgmt_status == "measured" else ""),
            mgmt_bytes,
            kind="shm",
        )

    total_ram = sum(x["bytes"] for x in lines if x["kind"] == "ram")
    total_disk = sum(x["bytes"] for x in lines if x["kind"] == "disk")
    total_shm = sum(x["bytes"] for x in lines if x["kind"] == "shm")

    errors: list[str] = []
    warnings: list[str] = []
    if c["log_contexts"] > c["dlt_max_contexts"]:
        errors.append(
            f"log.contexts count ({c['log_contexts']}) > bounds.dlt.max_contexts "
            f"({c['dlt_max_contexts']})"
        )
    if c["budget_ram_bytes"] > 0 and total_ram > c["budget_ram_bytes"]:
        warnings.append(
            f"total_ram ({total_ram}) > budget.ram_bytes ({c['budget_ram_bytes']})"
        )
    if c["budget_disk_bytes"] > 0 and total_disk > c["budget_disk_bytes"]:
        warnings.append(
            f"total_disk ({total_disk}) > budget.disk_bytes ({c['budget_disk_bytes']})"
        )
    if iox_on and budget_shm > 0 and total_shm > budget_shm:
        warnings.append(
            f"total_shm ({total_shm}) > iceoryx.budget_shm_bytes ({budget_shm})"
        )
    if iox_on and mgmt_status == "pending_measure":
        warnings.append(
            "roudi_mgmt pending_measure — run SIL once (or rebuild iceoryx) to fill "
            "generated/iox_shm_report.json; changing iceoryx.mgmt requires reconfigure+rebuild iceoryx"
        )

    return {
        "schema_version": "0.1",
        "caps": c,
        "constants": {
            "C_EVENT_RECORD": C_EVENT_RECORD,
            "C_DEBOUNCE_ENTRY": C_DEBOUNCE_ENTRY,
            "C_DLT_CTX": C_DLT_CTX,
            "C_PER_KEY_OH": C_PER_KEY_OH,
            "C_CHUNK_HDR": C_CHUNK_HDR,
        },
        "lines": lines,
        "total_ram_bytes": total_ram,
        "total_disk_bytes": total_disk,
        "total_shm_bytes": total_shm,
        "iceoryx_enabled": iox_on,
        "iceoryx_mgmt": iox_mgmt if iox_on else {},
        "iceoryx_mempools": iox_pools if iox_on else [],
        "roudi_mgmt_status": mgmt_status,
        "errors": errors,
        "warnings": warnings,
        "formula_doc": "gf_codegen.compose.mem_budget.FORMULAS (module docstring)",
    }


def fmt_bytes(n: int | None) -> str:
    """Bytes plus MiB for reviewable totals (1 MiB = 1024²)."""
    b = int(n or 0)
    mib = b / (1024 * 1024)
    return f"{b} B ({mib:.2f} MiB)"


def format_estimate_text(est: dict[str, Any]) -> str:
    """Human-readable block for gf-config UI / CLI."""
    out: list[str] = [
        "BL-MEM-BOUND estimate  "
        f"RAM={fmt_bytes(est['total_ram_bytes'])}  "
        f"DISK={fmt_bytes(est['total_disk_bytes'])}  "
        f"SHM={fmt_bytes(est.get('total_shm_bytes', 0))}",
        "SHM = iceoryx/RouDi POSIX shared memory "
        "(roudi_payload mempools + iceoryx_mgmt); not process heap RSS.",
        f"(constants: {est['constants']})",
        "RAM lines (process-local upper bound):",
    ]
    for ln in est["lines"]:
        if ln["kind"] != "ram":
            continue
        out.append(f"  {ln['name']}: {fmt_bytes(ln['bytes'])}  ← {ln['formula']}")
    out.append("DISK lines:")
    for ln in est["lines"]:
        if ln["kind"] != "disk":
            continue
        out.append(f"  {ln['name']}: {fmt_bytes(ln['bytes'])}  ← {ln['formula']}")
    shm_lines = [ln for ln in est["lines"] if ln["kind"] == "shm"]
    if shm_lines:
        out.append("SHM lines (iceoryx / RouDi shared memory):")
        for ln in shm_lines:
            out.append(f"  {ln['name']}: {fmt_bytes(ln['bytes'])}  ← {ln['formula']}")
        if est.get("roudi_mgmt_status") == "pending_measure":
            out.append(
                "  NOTE: change iceoryx.mgmt.* → reconfigure + rebuild iceoryx; "
                "mempool changes → compose + restart RouDi"
            )
    for e in est.get("errors") or []:
        out.append(f"ERROR: {e}")
    for w in est.get("warnings") or []:
        out.append(f"WARN: {w}")
    return "\n".join(out)
