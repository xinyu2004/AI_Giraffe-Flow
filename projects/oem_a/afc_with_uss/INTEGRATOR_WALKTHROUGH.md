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
| [interfaces/vehicle_gateway/](interfaces/vehicle_gateway/) | EgoMotion + FCM/FAPA 整包输入 |
| [interfaces/fcm_perception/](interfaces/fcm_perception/) | FCM 粗端口 `io_ports.hpp` |
| [interfaces/fapa_perception/](interfaces/fapa_perception/) | FAPA 粗端口 `io_ports.hpp` |
| [interfaces/uss_sensing/](interfaces/uss_sensing/) | USS |
| [oem/](oem/) | DBC + extract + manifest |
| [integration/wiring.yaml](integration/wiring.yaml) | **W0 粗端口连线基线** |
| [100_dbc/](../../../100_dbc/) | 金样 DBC + FCM_hpp / FAPA_hpp |

---

## 0b. 第一步：gf-config 粗端口对接（取代线下对表）

**不要在画布上连几十个字段。** 一条边 = 一包协议；字段细节留在 `100_dbc/*_hpp`。

```bash
gf-config projects/oem_a/afc_with_uss/project.yaml
# B 页：gateway → fcm / fapa / uss → planning
# 右侧 dataflow 点 ◀ 可折叠；导入时勾选「仅粗端口」
```

| 会上原来对的话 | 画布边 |
|----------------|--------|
| FCM 吃 Perception_In | gateway → `Perception_In_St` → perception.fcm |
| FCM 吐 MESSAGE_Out | fcm → `Perception_MESSAGE_Out_St` → planning |
| FAPA 吃 CanInfo | gateway → 三包 → perception.fapa |
| FAPA 吐 ADC Out | fapa → `IPC_ADC_Perception_Out_St` → planning |
| USS 区划 | uss → `UssZones` → planning |
| 规划控车 | planning → `Trajectory` → gateway → **MCU/车身** |
| 车身源 | **MCU/车身** → `VehicleBus` → gateway |

画布技巧：双击模块可改 **In/Out 所在边**（gateway 建议 In 在下）；右键空白可「添加 MCU/车身 节点」。

---

## 1. 适配顺序

```text
① 选定 SOA Apps（uss + fcm + fapa + planning）
② 粗端口 hpp → interfaces/（金样留 100_dbc）
③ oem extract / oem_import.dbc + oem_import.yaml
④ wiring.yaml（W0 已有基线）
⑤ req.yaml
⑥ compose → lineage → generate
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
# 日常：gf-config 打开本项目 → 保存（自动 compose）→ Generate (Ctrl+G)
# CI / 无 GUI：
python -m gf_codegen.compose --project projects/oem_a/afc_with_uss/project.yaml
```

实施规格：[IMPLEMENTATION.md](../../../tools/codegen/IMPLEMENTATION.md) · 总计划：[P0_PLAN.md](../../../docs/zh/operations/P0_PLAN.md)

---

## 2.1 如何审本项目？用 gf-config / gf-codegen 还是 GMT？

### 工具分工（配套一起用，不互相替代）

| 工具 | 管什么 | 不管什么 |
|------|--------|----------|
| **`gf-config`** | 改 req/wiring、**保存自动 compose**、**Generate** | CI 无显示器 |
| **`gf-codegen`** | lint / suggest / **generate** / import；compose 仅库 + `python -m gf_codegen.compose` | GUI |
| **GMT** | 读已有 SOR 做 architect / measure | 写 wiring、compose |

```text
审「输入对不对 / 保存后 SOR」     →  gf-config（主）
审「无 GUI 时 CI 合成」           →  python -m gf_codegen.compose
审「拓扑/度量」                   →  GMT architect / measure
```

### 工具已就绪时——命令审（推荐）

```bash
# 在仓库根目录
pip install -e "tools/codegen[dev]" -e "tools/config"
# 作者路径：开 gf-config → 保存 → Generate
# 或 CI：
python -m gf_codegen.compose --project projects/oem_a/afc_with_uss/project.yaml
# 看 reports/signal_lineage_report.yaml
gf-codegen lint projects/oem_a/afc_with_uss/gf.sor.json
gf-codegen generate projects/oem_a/afc_with_uss/gf.sor.json --out projects/oem_a/afc_with_uss/generated/
```

| 阶段 | 主工具 | 你做什么 |
|------|--------|----------|
| 输入评审 | gf-config / 编辑器 | 改 yaml/hpp/dbc |
| 合成与门禁 | **gf-config 保存** 或 `python -m gf_codegen.compose` | 看 lineage |
| C++ API | **Generate** / `gf-codegen generate` | Proxy/Skeleton |
| 只读检查 | **GMT** | architect lineage |
| 联调 | iceoryx / MCU smoke | 脚本 |

### 无 CLI 时——人工审输入清单（仍可用）

| # | 审什么 | 打开 | 通过标准 |
|---|--------|------|----------|
| 1 | 本 SKU 只要哪些 App | [wiring.yaml](integration/wiring.yaml) deployments | 仅有 gateway + `sensing.uss` + `perception.front` + `planning.driving`；**无**环视/泊车/MCU |
| 2 | hpp 路径存在且为本项目 | wiring `modules[].hpp` → [interfaces/](interfaces/) | 路径可打开；未引用已删的 `Requirement/` |
| 3 | provide/require 闭环 | deployments + dataflows | 每个 require 有 provider；边与表一致 |
| 4 | struct ↔ semantic | bindings + hpp | `UssZones` / `FrontObjectList` / `EgoMotion` 名字对得上 |
| 5 | DBC 归属 | [oem_import.yaml](oem/oem_import.yaml) | Ego→gateway；PDC/USS→`module_owned: sensing.uss`；无逐探头进 SOR |
| 6 | 验收意图 | [req.yaml](req.yaml) | `required_services` 含 EgoMotion、UssZones、FrontObjectList、Trajectory |
| 7 | OEM 主图叙事 | 对照 [PROCESS_ROLES.md](../../PROCESS_ROLES.md) | 主图只有三个 SOA App；gateway 是 Adapter；RouDi 不出现 |

数据流应能口述：

```text
CAN → gateway ─Ego─► uss ─UssZones─► front ─FrontObjectList─► planning
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
