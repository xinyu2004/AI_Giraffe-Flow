# carla_scenarios

CARLA Client A — product scenario suite for AFC（布景 + IC；连续控车应走 Giraffe→bridge）。

**文档（架构 / 分层 / 门禁 / 已知问题）：**

- 中文：[docs/zh/sku/afc_no_uss/scenarios.md](../docs/zh/sku/afc_no_uss/scenarios.md)
- English：[docs/en/sku/afc_no_uss/scenarios.md](../docs/en/sku/afc_no_uss/scenarios.md)

```bash
cd carla_scenarios
python3 run_cases.py cases/longitudinal   # batch → results/runs/<ts>/
python3 cases/longitudinal/acc.py         # single case (no results/)
bash scripts/check_spawn_import_gate.sh   # spawn import 门禁
```

Defaults: `carla.env`。实现：`src/spawn` + `src/layouts` + `src/lib`。产品案：`cases/`（manifest 只列清单）。

**与 gf-config 对齐相机**：compose 后读 SKU `generated/camera_contract.json`（`GF_PROJECT_DIR` / `GF_CAMERA_CONTRACT`；无本地 camera 几何）。详见 [frame_ingest_roles.md](../docs/zh/sku/afc_no_uss/frame_ingest_roles.md)。
