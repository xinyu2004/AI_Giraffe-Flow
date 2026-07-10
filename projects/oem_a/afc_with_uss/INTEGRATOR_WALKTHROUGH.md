# 集成工程师走查：OEM A / AFC + USS

> 第一版集成准备入口。  
> [MODULE_INTERFACE_LAYOUT.md](../../MODULE_INTERFACE_LAYOUT.md) · [PROCESS_ROLES.md](../../PROCESS_ROLES.md)

---

## 0. 归属（project-only）

| 东西 | 放哪 |
|------|------|
| DBC / manifest | 本项目 `oem/` |
| 模块 `io_types.hpp`（外仓常只交这个） | 本项目 `interfaces/` |
| 连线 / SKU | `integration/wiring.yaml`、`req.yaml` |
| 平台 API | `middleware/`（不是模块 IO） |
| Golden | 本项目稳定后放 `golden/`；主示范见 [`oem_b/adc_full/golden/`](../../oem_b/adc_full/golden/) |

```text
外仓只交 hpp → 落入本项目 interfaces/
DBC 跟车型 → 本项目 oem/
wiring 引用上述路径 → compose →（可选）与 golden 对照
```

本项目已有：

| 路径 | 内容 |
|------|------|
| [interfaces/uss_sensing/](interfaces/uss_sensing/) | USS |
| [interfaces/perception_front/](interfaces/perception_front/) | 前视 |
| [oem/](oem/) | DBC + manifest |
| [integration/wiring.yaml](integration/wiring.yaml) | 连线 |

---

## 1. 适配顺序

```text
① 选定 SOA Apps（本项目：uss + front + planning.driving）
② 外仓/模块 hpp → interfaces/
③ oem_import.dbc + oem_import.yaml
④ wiring.yaml
⑤ req.yaml
⑥ compose → lineage →（有 golden 则 diff）→ generate
```

---

## 2. 连线结果

```text
CAN → gateway ─EgoMotion─► sensing.uss ─UssZones─► perception.front ─FrontObjectList─► planning.driving
```

| process | 类别 |
|---------|------|
| `adapter.vehicle_can_gateway` | Adapter |
| `sensing.uss` / `perception.front` / `planning.driving` | SOA App |

```bash
gf-codegen compose --project projects/oem_a/afc_with_uss/project.yaml
```

---

## 3. Golden（对照用的「正确答案」SOR）

### 3.1 是什么

**Golden** = 一份已人工确认过的 `gf.sor.json` **快照**，当作本项目集成正确时的参考输出。

本仓库主示范：[`projects/oem_b/adc_full/golden/gf.sor.json`](../../oem_b/adc_full/golden/gf.sor.json)。  
`afc_with_uss` 在 compose 跑通并评审通过后，应自建 `projects/oem_a/afc_with_uss/golden/gf.sor.json`（与 ADC 的 DBC/模块不同，**不要共用一份**）。

### 3.2 干什么用

```text
DBC + hpp + wiring + req
        ↓ compose
   新生成的 gf.sor.json
        ↓ diff / CI
   golden/gf.sor.json（已知正确）
```

| 用途 | 说明 |
|------|------|
| **回归** | 改 wiring / DBC / codegen 后，输出应与 golden 一致，或只有**预期内**的 diff |
| **验收** | `req.yaml` → `acceptance.sor_golden` 指向本项目 golden；CI 据此判定 |
| **样例** | 新人 / 工具开发直接打开 golden，看完整 SOR 长什么样 |
| **防漂移** | 避免工具静默改坏字段、或手改 SOR 无人发现 |

类比：单元测试里的 **golden file / snapshot**——不是业务逻辑本身，而是锁定「已知正确输出」。

### 3.3 不是什么

| 不是 | 是 |
|------|-----|
| 不是 OEM 架构报告正文（报告看 SOA App + semantic） | 是工程侧对照快照 |
| 不是必须刷进量产镜像的运行时文件 | 是主机 / CI 用 |
| 不是永远不能改 | **有意**变更接口或连线时，更新 golden 并走评审 |

### 3.4 何时更新 golden

| 情况 | 动作 |
|------|------|
| 修 bug、改工具，期望 SOR **不变** | **不改** golden；CI diff 应为空 |
| 有意增删服务、改字段、改 wiring 拓扑 | compose → 人工审 diff → **提交新 golden** + 更新 `req.yaml` 路径（若有） |
| 新项目第一次跑通 | 评审通过后 **新建** `golden/gf.sor.json` |

日常改 wiring 联调时：先看 lineage 红项；**不要**每次试验都覆盖 golden。只有「这一版就是交付基线」时才更新。

### 3.5 和本项目的关系

| 项目 | Golden |
|------|--------|
| `oem_b/adc_full` | 已有主示范 |
| `oem_a/afc_with_uss`（本项目） | 第一版 compose 稳定后补 `golden/` |
| `oem_a/afc_no_uss` | 同上，各自一份 |

`req.yaml` 示例字段：

```yaml
acceptance:
  sor_golden: projects/oem_a/afc_with_uss/golden/gf.sor.json   # 本项目有后再填
  lineage_required: true
```

---

## 4. 检查清单

- [ ] hpp 只在本项目 `interfaces/`，DBC 只在本项目 `oem/`
- [ ] wiring 路径可打开；未把 middleware 当模块 IO
- [ ] require 均有 provider；USS 原始帧不逐帧进 SOR
- [ ] `req.yaml` 与 deployments 一致
- [ ] 理解 golden：对照用；有意变更才更新；不与他项目共用
