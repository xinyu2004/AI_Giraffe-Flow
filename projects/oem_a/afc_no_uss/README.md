# oem_a / afc_no_uss — AFC 前视（无 USS）

P3-5：`Perception_*` + `Trajectory`；帧摄入 / CARLA / Foxglove。详见 [SIM_SPIKE.md](SIM_SPIKE.md)。

## 验收（主路径）

```bash
# 1) gf-config：打开本工程 → 页 1「帧摄入」确认 tip 源 → Verify
# 2) 编译并跑 SIL（增量；默认不跑 ctest）
bash projects/oem_a/afc_no_uss/scripts/compile_sil.sh
bash projects/oem_a/afc_no_uss/scripts/run_sil.sh
# Foxglove Studio → ws://127.0.0.1:8765（GMT_depend）

# 板端产品入口（拷整个 runtime/）：
#   systemctl enable --now giraffe-em   # 见 common/deploy/systemd/
# 主机调试：
#   ./build-sil/runtime/bin/giraffe_launch
#   或 GF_GMT_DEPEND=0 bash …/run_sil.sh
# 作者 yaml 进包（非产品）：GF_STAGE_PLATFORM=1 bash …/compile_sil.sh

# 交叉：bash …/compile_hil.sh   （可选 GF_STAGE_HIL=1）
```

原则：[CONFIG_RUNTIME_POLICY.md](../../../docs/zh/operations/CONFIG_RUNTIME_POLICY.md)（白名单可 JSON；行为须编译冻结；其它 project 同原则）。

## 配置

- `req.yaml`（含 `frame_ingest` / `observability`）— **用 gf-config 编辑**
- `integration/wiring.yaml` / `platform/*`
- CARLA tip 实现：`tools/carla_bridge/`（由 `frame_ingest.bridge` 控制是否启动）

参考（只读）：`projects/oem_a/afc_with_uss/`。
