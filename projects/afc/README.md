# AFC — 前视 ADAS（无 USS）

`Perception_*` + `Trajectory`；帧摄入 / CARLA / Foxglove。SIL：`scripts/compile_sil.sh` → `scripts/run_sil.sh`。

## 验收（主路径）

```bash
# 1) gf-config：打开本工程 → Verify(+Generate)
# 2) 编译并跑 SIL
bash projects/afc/scripts/compile_sil.sh
bash projects/afc/scripts/run_sil.sh
# Foxglove Studio → ws://127.0.0.1:8765（GMT_depend）

# 板端：systemctl enable --now giraffe-em  # common/deploy/systemd/
# 主机：./build-sil/runtime/bin/giraffe_launch
# 或 GF_GMT_DEPEND=0 bash projects/afc/scripts/run_sil.sh
```

原则：[CONFIG_RUNTIME_POLICY.md](../../docs/zh/operations/CONFIG_RUNTIME_POLICY.md)

## 配置

- `req.yaml`（含 `frame_ingest` / `observability`）— **用 gf-config 编辑**
- `integration/wiring.yaml` / `platform/*`
- CARLA：`tools/carla_bridge/`

## Verify

见 `scripts/verify/`（DoIP / observability / EM / PHM 等；无 USS 专用案）。

## Golden

`golden/gf.sor.json` = compose + 人工审定后的 CI 对照快照（默认 gitignored）。主示范见 [`../adc/golden/`](../adc/golden/)。刷新：

```bash
# gf-config 保存后，或：
python -m gf_codegen.compose --project projects/afc/project.yaml
# 可选写入 golden：
GF_FUSA_PACK_UPDATE_GOLDEN=1 bash projects/afc/scripts/generate_fusa_artifacts.sh
```
