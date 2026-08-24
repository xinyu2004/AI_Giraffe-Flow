# samples（SKU 数据包）

路径：`projects/afc/samples/`

- **用途**：inject 金样、collector/DTC 演示片段、`stage.sh` 拷到与 HIL 同构的真实路径。
- **不放**：产品功能场景（ACC/AEB）——见仓库根 `carla_scenarios/`。
- **不冻结进 gf-config**：运行相机路径仍是 `/tmp/...` 或板端路径；金样用变量 + stage。

## 变量

```bash
export GF_SAMPLES_DIR=projects/afc/samples
export GF_STAGE_ROOT=/tmp/gf_stage          # 或 HIL 约定根
export GF_SCENARIOS_DIR=carla_scenarios       # 产品 case，可选
```

## stage

```bash
./samples/stage.sh --inject continuous
# 打印 GF_INJECT_SESSION / GF_INJECT_FRAMES_DIR 等 export
```
