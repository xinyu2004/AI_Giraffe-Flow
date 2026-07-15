# dds

**Default DDS vendor: Eclipse CycloneDDS** (when `req.bindings` includes `dds` / `GF_WITH_DDS=ON`).

| Mode | When | Behavior |
|------|------|----------|
| **stub** (default offline) | no `middleware/third_party/cyclonedds` | In-process pub/sub loopback (`gf_ara::com_dds`) |
| **cyclone** | tree present + `GF_DDS_BACKEND=cyclone` | Links `ddsc`; `BackendName()` → `cyclonedds` |

```bash
bash scripts/smoke_bd_stub.sh
gf-codegen emit-idl path/to/gf.sor.json --out generated/idl/
bash scripts/run_idlc.sh generated/idl/gf_types.idl   # SKIP if idlc missing
```

Pin: [deps/versions.lock.md](../../../deps/versions.lock.md) · Parent: [bindings/README.md](../README.md)
