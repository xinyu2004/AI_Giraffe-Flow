# common/ — launch & deploy templates

**Contract:** these are **templates**. Copy into a SKU once, then the SKU owns the copy forever.

```bash
# From repo root — only creates missing files under projects/<oem>/<sku>/scripts/
bash common/bootstrap_sku_scripts.sh afc
```

| Rule | Meaning |
|------|---------|
| No long-term `source common/...` | SKU scripts must not depend on this tree after bootstrap |
| No `sil_` / `hil_` in template names | Host vs cross is a parameter / SKU wrapper name |
| Product entry | `common/deploy/systemd` or `init.d` → `gf_em_daemon` |
| Debug only | optional `giraffe_launch` on host |
| Abnormal child exit | EM stops the machine; board recovers via unit `Restart=on-failure` |

## Layout

```text
common/
  launch/           project_env.sh compile.sh
                    run.sh gmt_depend.sh obs_inject.sh
  deploy/
    systemd/        giraffe-em.service.example
    init.d/         giraffe-em.example
  bootstrap_sku_scripts.sh
```

## Mapping into SKU scripts/

| Template | Typical SKU name(s) |
|----------|---------------------|
| `project_env.sh` | `_common.sh` |
| `compile.sh` | `compile_sil.sh`, `compile_hil.sh` (fork after copy) |
| `run.sh` | `run_sil.sh`, `run_hil.sh` |
| `gmt_depend.sh` | `GMT_depend_launch.sh` |
| `obs_inject.sh` | `obs_inject.sh` |

After copy: set `TAG`, `APP_BINS`, PHM defaults, and whether video contract / USS exists.
