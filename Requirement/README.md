# Requirement（平台归档 + 模块 IO 示例）

本目录**不再**存放车型集成工程。集成侧四类输入已迁至 [`projects/`](../projects/)。

## P0 必留文件

| 路径 | 用途 | 说明 |
|------|------|------|
| [`modules/**/io_types.hpp`](modules/) | 模块 IO 形状示例 | 真实模块在各业务仓；wiring 里登记路径 |
| [`modules/README.md`](modules/README.md) | 模块工程师说明 | — |
| [`vehicle_demo.sor.json`](vehicle_demo.sor.json) | **Golden SOR** | CI / `req.yaml` acceptance 对照 |
| [`archive/Demo_Car_*.dbc`](archive/) | 原始车身 DBC 归档 | 溯源用，不参与 `compose` |

## 已迁出 / 已删除（勿在本目录再找）

| 原路径 | 现位置 |
|--------|--------|
| `oem_import.dbc` / `oem_import.yaml` | `projects/oem_demo/vehicle_demo/oem/` |
| `dbc_vehicle_can.extract.yaml` | 同上 |
| `vehicle_demo.project.yaml` | `projects/oem_demo/vehicle_demo/project.yaml` |
| `integration/*.wiring.yaml` | `projects/.../integration/wiring.yaml` |
| `SOR_EXTRACTION.md` | 并入 [sor-authoring.md](../docs/zh/architecture/sor-authoring.md) |
| `modules/**/module.meta.yaml` | 已废弃，内容在 wiring |

## 可选（你可自行删除）

| 路径 | 说明 |
|------|------|
| `app.xlsx` / `Nullmax.xlsx` | SOA 表来源；对应 hpp 已导出，删 xlsx 不影响 P0 |

## 集成工程师入口

```bash
gf-codegen compose --project projects/oem_demo/vehicle_demo/project.yaml
```

文档：[sor-authoring.md](../docs/zh/architecture/sor-authoring.md) · [WORKFLOW.md](../docs/zh/operations/WORKFLOW.md)
