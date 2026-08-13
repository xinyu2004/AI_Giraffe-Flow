# samples (SKU data packs)

Path: `projects/oem_a/afc_no_uss/samples/`

- **For**: inject goldens, collector/DTC demos, `stage.sh` copy onto HIL-like paths.
- **Not for**: product scenarios (ACC/AEB) — see repo-root `carla_scenarios/`.
- **Not frozen in gf-config**: runtime tip paths stay `/tmp/…` or board paths; goldens use variables + stage.

```bash
export GF_SAMPLES_DIR=projects/oem_a/afc_no_uss/samples
export GF_STAGE_ROOT=/tmp/gf_stage
export GF_SCENARIOS_DIR=carla_scenarios
./samples/stage.sh --inject continuous
```
