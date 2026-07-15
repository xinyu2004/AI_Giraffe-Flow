# OEM A / AFC（无 USS）

前视一体机项目。集成工程师工作区。

## SOA Apps（OEM 主图）

| process | 角色 |
|---------|------|
| `perception.front` | 前视感知 → `FrontObjectList` |
| `planning.driving` | 行车规划 → `Trajectory` |

## Adapter（边界）

| process | 角色 |
|---------|------|
| `adapter.vehicle_can_gateway` | CAN → `EgoMotion` |

**无** `sensing.uss` / 泊车 / MCU。

```text
CAN → vehicle_can_gateway ─EgoMotion─► perception.front ─FrontObjectList─► planning.driving
```

角色总表：[PROCESS_ROLES.md](../../PROCESS_ROLES.md)

```bash
```bash
# 仓库根
python -m gf_codegen.compose --project projects/oem_a/afc_no_uss/project.yaml
gf-codegen lint projects/oem_a/afc_no_uss/gf.sor.json
```

（日常请用 **gf-config** 打开本项目并保存，自动 compose。）
```
