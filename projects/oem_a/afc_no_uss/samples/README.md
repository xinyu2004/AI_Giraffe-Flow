# afc_no_uss samples

SKU demo assets (inject packs, collector/DTC goldens, stage).  
**Not** product scenarios — those live at repo `carla_scenarios/`.

Full docs (symlink): [`../docs`](../docs) → `docs/zh/sku/afc_no_uss/`.

## Variables

| Variable | Default | Role |
|----------|---------|------|
| `GF_SAMPLES_DIR` | this directory | Source of goldens |
| `GF_STAGE_ROOT` | `/tmp/gf_stage` | HIL-like runtime copy target |
| `GF_SCENARIOS_DIR` | `$REPO/carla_scenarios` | Product cases (ACC/AEB) |

## Quick start

```bash
export GF_SAMPLES_DIR=$PWD/samples
./samples/stage.sh --inject continuous
# then run_sil / inject with paths printed by stage
```
