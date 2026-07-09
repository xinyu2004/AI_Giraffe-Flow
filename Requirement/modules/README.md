# 自研模块 IO（模块工程师只交 hpp）

## 交付物

| 谁 | 交什么 | 不交什么 |
|----|--------|----------|
| **模块工程师** | `io_types.hpp` | JSON、YAML、`module.meta.yaml`、fragment |
| **系统工程师** | 在 [`projects/.../integration/wiring.yaml`](../projects/oem_demo/vehicle_demo/integration/wiring.yaml) 登记 hpp 路径并连线 | — |

```text
模块仓 io_types.hpp
    →（compose 时内存解析，不落盘 JSON）
    → integration/wiring.yaml 声明谁订谁
    → gf.sor.json
```

## 示例目录（本仓参考）

| 目录 | 来源 | process id（在 wiring 中登记） |
|------|------|-------------------------------|
| [mcu_cp_gateway/](mcu_cp_gateway/) | app.xlsx Platform | `adapter.mcu_cp_gateway` |
| [perception_parking/](perception_parking/) | app.xlsx Perception | `perception.parking` |
| [perception_driving/](perception_driving/) | Nullmax.xlsx | `perception.driving.nullmax` |

## 集成工程师命令

```bash
gf-codegen compose --project projects/oem_demo/vehicle_demo/project.yaml
```

见 [projects/oem_demo/vehicle_demo/README.md](../projects/oem_demo/vehicle_demo/README.md)。
