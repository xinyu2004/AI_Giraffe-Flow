# dds

**Default DDS vendor: Eclipse CycloneDDS** (when `req.bindings` includes `dds` / `GF_WITH_DDS=ON`).

| Mode | When | Behavior |
|------|------|----------|
| **stub** (default offline) | `GF_DDS_BACKEND=stub` 或无 third_party | In-process pub/sub loopback |
| **cyclone** | tree + `GF_DDS_BACKEND=cyclone` | **Real** `ddsc` pub/sub via `GfBlob.idl` |

```bash
bash scripts/bootstrap_deps.sh          # fetch cyclonedds 0.10.5
bash scripts/smoke_bd_cyclone.sh        # real ≥1 event
bash scripts/smoke_bd_stub.sh           # offline stub
```

**主链 SIL 仍为 iceoryx** — 见 [CYCLONEDDS_BYPASS.md](../../../docs/zh/operations/CYCLONEDDS_BYPASS.md)。  
**vsomeip** 保持 stub。

Pin: [deps/versions.lock.md](../../../deps/versions.lock.md) · Parent: [bindings/README.md](../README.md)
