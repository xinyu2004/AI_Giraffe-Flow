# OEM A / AFC（有 USS）

与 `afc_no_uss` 同属前视产品线；本 SKU **多独立超声 SOA App**。

## SOA Apps（OEM 主图）

| process | 角色 |
|---------|------|
| `sensing.uss` | 超声 → `UssZones` |
| `perception.front` | 前视（可订 `UssZones`）→ `FrontObjectList` |
| `planning.driving` | 行车规划 → `Trajectory` |

## Adapter

| process | 角色 |
|---------|------|
| `adapter.vehicle_can_gateway` | CAN → `EgoMotion`（PDC/USS 原始归 `sensing.uss`） |

```text
CAN → gateway ─EgoMotion─► sensing.uss ─UssZones─► perception.front ─FrontObjectList─► planning.driving
                 └───────────────────────────────► perception.front
```

对比无 USS 变体：[../afc_no_uss/](../afc_no_uss/) · 角色总表：[PROCESS_ROLES.md](../../PROCESS_ROLES.md)

**集成走查（含 Golden 说明）：** [INTEGRATOR_WALKTHROUGH.md](INTEGRATOR_WALKTHROUGH.md)  
**本项目接口：** [interfaces/](interfaces/) · 布局：[MODULE_INTERFACE_LAYOUT.md](../../MODULE_INTERFACE_LAYOUT.md)

```bash
# 产品主路径：gf-config → compile_sil → run_sil（live 开则自动 Foxglove）
bash projects/oem_a/afc_with_uss/scripts/compile_sil.sh
bash projects/oem_a/afc_with_uss/scripts/run_sil.sh

# HIL 交叉编译（需 aarch64 工具链）
bash projects/oem_a/afc_with_uss/scripts/compile_hil.sh

# 验证 smoke（非产品路径）
bash scripts/verify/oem_a_afc_with_uss/smoke_sil_multiproc.sh
```
