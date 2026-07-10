# Requirement（平台归档 + 模块 IO 示例）

本目录**不再**存放车型集成工程。集成侧四类输入在 [`projects/`](../projects/)。

## P0 必留文件

| 路径 | 用途 |
|------|------|
| [`modules/**/io_types.hpp`](modules/) | 模块 IO 示例（含独立 **uss_sensing**） |
| [`modules/README.md`](modules/README.md) | 模块工程师说明 |
| [`vehicle_demo.sor.json`](vehicle_demo.sor.json) | Golden SOR |

## archive/（可选，非 P0）

[`archive/`](archive/) 目前为空占位；原 `Demo_Car_*.dbc` 随意样例已删除，**非 P0 必留**。正式 OEM 全量通信矩阵的收纳流程另议（TBD）。

## 可选

| 路径 | 说明 |
|------|------|
| `app.xlsx` / `Nullmax.xlsx` | SOA 表来源；hpp 已导出则可删 |

## 集成入口

```bash
gf-codegen compose --project projects/oem_demo/vehicle_demo/project.yaml
```
