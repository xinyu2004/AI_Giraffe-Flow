# Inject — three modes (this SKU)

| Directory | Mode | Typical env |
|-----------|------|-------------|
| `continuous/` | File continuous replay | `GF_INJECT_SESSION` + `GF_INJECT_MODE=continuous` |
| `playhead/` | GMT playhead | `GF_INJECT_MODE=playhead` (session optional) |
| `dut/` | B2 single DUT | `GF_INJECT_DUT` + session |

Mutex: with `ego_source=inject`, gateway must **not** publish EgoMotion.

```bash
./samples/stage.sh --inject playhead
export GF_EGO_SOURCE=inject
bash projects/oem_a/afc_no_uss/scripts/run_sil.sh
```
