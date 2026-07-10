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

```bash
gf-codegen compose --project projects/oem_a/afc_with_uss/project.yaml
```
