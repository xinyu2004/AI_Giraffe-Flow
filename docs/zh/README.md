# 中文文档

**English:** [../en/README.md](../en/README.md) · 根: [../../README_zh.md](../../README_zh.md)

Lightweight middleware + toolchain for cross-platform SOA systems. Closed-loop virtual world, Foxglove, and CI/CD — see it, stress it, pass it on the bench; the hardware is the last mile.

## 三条主线（从根 README 进来）

| 主线 | 入口 |
|------|------|
| **gf-config** | [../../tools/gf-config/README_zh.md](../../tools/gf-config/README_zh.md) · [architecture/sor-authoring.md](architecture/sor-authoring.md) · [operations/WORKFLOW.md](operations/WORKFLOW.md) |
| **Giraffe 模块** | [../../middleware/README.md](../../middleware/README.md) · [architecture/DESIGN.md](architecture/DESIGN.md) · [../../projects/afc/](../../projects/afc/)（闭环载荷 SKU） |
| **GMT** | [../../tools/gmt/README_zh.md](../../tools/gmt/README_zh.md) · [../../tools/gmt_board/README.md](../../tools/gmt_board/README.md) · [operations/OBSERVABILITY_DEMO.md](operations/OBSERVABILITY_DEMO.md) |

## 专题索引

| 文档 | 说明 |
|------|------|
| [architecture/DESIGN.md](architecture/DESIGN.md) | 总体设计（中间件 + 工具链；感知/规划为载荷） |
| [architecture/sor-authoring.md](architecture/sor-authoring.md) | SOR / compose |
| [architecture/heterogeneous-compute.md](architecture/heterogeneous-compute.md) | AP + MCU |
| [operations/ROADMAP.md](operations/ROADMAP.md) | 路线图 |
| [operations/CONFIG_RUNTIME_POLICY.md](operations/CONFIG_RUNTIME_POLICY.md) | 白名单 vs 行为；板端零 yaml / 零 Python |
| [operations/AP_LITE_BACKLOG.md](operations/AP_LITE_BACKLOG.md) | 后置项（含 `BL-BOARD-NO-PY` · `BL-GMT-FOX-PY`） |
| [operations/WORKFLOW.md](operations/WORKFLOW.md) | 操作流程 |
| [operations/OBSERVABILITY_DEMO.md](operations/OBSERVABILITY_DEMO.md) | tap / Foxglove（C `:8765`）/ 回灌 |
| [driving/fcm_gold_and_planning_lite.md](driving/fcm_gold_and_planning_lite.md) | FCM 金样 + planning |
| [driving/planning_lon_v4.md](driving/planning_lon_v4.md) | 规划 v4 |
| [sku/afc/scenarios.md](sku/afc/scenarios.md) | CARLA 场景 |
| [../../devops/README.md](../../devops/README.md) | 台架 CI → CD last mile（真机） |
| [dependencies/THIRD_PARTY_EVALUATION.md](dependencies/THIRD_PARTY_EVALUATION.md) | 三方库 |

阅读顺序：根 [README_zh.md](../../README_zh.md) → 上表三条主线 → 需要时再开 DESIGN / ROADMAP。
