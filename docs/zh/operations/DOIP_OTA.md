# DoIP / OTA（P3-4）

> **状态：** 桌面 SIL 会话级路径已收口。真 RAUC 刷写 / 真板 → **P3z**。  
> 相关：[PHM_OTA_PAUSE.md](PHM_OTA_PAUSE.md) · [OTA_SPIKE.md](OTA_SPIKE.md)（P2 选型史）· [MIDDLEWARE_CONFIG_PLAN.md](MIDDLEWARE_CONFIG_PLAN.md) §3.6–3.7 · `middleware/diag` · `middleware/ucm` · GMT OTA 页

## 结论（先读）

| 项 | 口径 |
|----|------|
| 配置真源 | **gf-config** → `platform/diag.yaml` / `ucm.yaml`（GMT **不写**配置） |
| 操作面 | **GMT → OTA/UDS**：共用 DoIP；单选 **OTA / DEM / Collector**；按 yaml 模式发 UDS → UCM 编排 |
| 下载 SID | 默认 **0x38** `request_file_transfer`；可选 **0x34** / SIL **0x31** 捷径 |
| 传输 | ISO **14229** 父能力；ISO **13400** DoIP 为子传输（不可单独开） |
| 刷写后端 | SIL stub（写 `.activated` / magic 校验）；**真 RAUC → P3z** |
| 失败可观测 | Collector 事件 `ucm/ota_failed` |

## 数据流

```text
gf-config 写 diag.yaml（standards / doip / timing / ota_transfer）
        │
run_sil ──► gf_doip_ota_server（ISO 13400 开时自动拉起）
        │         ▲
        │         │ DoIP TCP + UDS
GMT OTA 连接 ──────┘
        │
        ▼
UdsDispatcher → UCM OtaOrchestrator → PackageManager →（stub）落盘/Activate
                     │
                     └─ 失败 → Collector ota_failed
```

## `diag.yaml` 关键字段

| 块 | 作用 |
|----|------|
| `standards.iso_14229_uds` | UDS 父能力（含 NRC） |
| `standards.iso_13400_doip` | DoIP 传输；依赖 14229 |
| `doip.*` | `logical_address` / `tester_address` / `tcp_port`（与 GMT Host:Port 对齐） |
| `timing` | `s3_server_ms`、`tester_present_period_ms`（须 **&lt; S3**）、`p2_*`、`security_delay_ms` |
| `ota_transfer.mode` | `request_file_transfer` \| `request_download` \| `routine_sil` |
| `ota_transfer.require_*` | 是否强制 ProgrammingSession / SecurityAccess |
| `ota_transfer.max_block_length` | 0x36 单块上限 |

示例见 `projects/oem_a/afc_with_uss/platform/diag.yaml`。

### 传输模式对照

| `mode` | SID 序列 | 用途 |
|--------|----------|------|
| `request_file_transfer` | 0x38 → 0x36… → 0x37 | DoIP / 以太网默认 |
| `request_download` | 0x34 → 0x36… → 0x37 | 经典内存下载 |
| `routine_sil` | 0x31 F100 | SIL 捷径，无字节管道 |

## gf-config（页 2 · 诊断）

- **doip / timing / ota_transfer** 可折叠；下载 SID 下拉显式显示 `0x38` / `0x34` / `0x31`。
- **0x27 插件路径不写进 yaml**：在 **GMT → OTA** 本地记住；板端用 `GF_DIAG_SEC_PLUGIN`。
- **ucm** 子页：编排开关、目标 FG、失败是否 Rollback（不是刷写进度 UI）。

## GMT（OTA/UDS 页）

> **2026-08-04：** 原独立 Collector 页已并入本 Tab；与 DEM 共用上方 DoIP 连接与下方 **UDS 交互**日志。

| 控件 | 行为 |
|------|------|
| Standards / 传输模式 / 会话时序 | **只读**，跟从已加载项目的 `diag.yaml` |
| Host:Port · 连接 | DoIP TCP + RoutingActivation；连接后按 yaml 周期发 **0x3E** |
| 模块单选 | **OTA** · **DEM** · **Collector**（配置仍只在 gf-config） |
| Package id / Artifact · Start OTA | 包逻辑名 vs 主机产物路径；按 mode 跑完整序列（OTA 选中时模块区收短，UDS 日志紧挨 Start OTA） |
| DEM | `0x19` 读 DTC 列表 · `0x14` 清除（DEM-lite；非 Classic DEM 编辑器） |
| Collector | 本机 NDJSON **或** UDS `0x31 01 F201` 读板端环缓 Snapshot（NDJSON） |
| UDS 交互 | 各模块步骤共用同一日志区 |

**须先「加载项目」**（与回灌相同）；未开 ISO 13400 时连接禁用。

## SIL 一键路径

```bash
# 1) 假包（可选）
bash scripts/make_sil_swu.sh /tmp/gf_demo.swu

# 2) 编译 + 跑 SIL（diag 开 13400 时会起 gf_doip_ota_server）
#    见 projects/.../scripts/run_sil.sh
#    默认写 GF_COLLECTOR_STORE=${BUILD}/runtime/collector/events.ndjson

# 3) 自动化冒烟
bash scripts/verify/oem_a_afc_with_uss/smoke_doip_ota.sh

# 4) 或开 GMT → 加载 project.yaml → OTA/UDS → 连接 → Start OTA
#    （同页可切 DEM 读/清 DTC，或 Collector 读环缓）
```

### 观测演示（Collector / DEM）

路径：**PHM 真实故障 → Collector `ReportEvent` → PER（`GF_PER_DIR`）→ DoIP 0x19 `ReloadDtcsFromPer`**。  
没有进程内假种数；环缓 NDJSON 看 `GF_COLLECTOR_STORE`。

```bash
# 断言：uss AliveMissed → NDJSON + PER → UDS 0x19 读到 0xC01234
bash scripts/verify/oem_a_afc_with_uss/smoke_phm_dem_doip.sh

# 交互：DoIP 开时默认对 uss 短注 PHM（GF_PHM_FAULT_MS=500）
bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
# 另开终端：
GMT gui --project projects/oem_a/afc_with_uss
# → OTA/UDS 连接 → 等 ~1s → DEM「读取 DTC」
# Collector「本机文件」→ …/runtime/collector/events.ndjson
```

**关闭 PHM 注入：** `GF_PHM_FAULT_MS=0 bash …/run_sil.sh`。  
`dtc_map` 事件键须与 `AliveMissed` / `DeadlineMissed` / `ota_failed` 等 `event_id` 一致。

环境变量覆盖（服务端 / smoke，可选）：`GF_DOIP_PORT`、`GF_OTA_TRANSFER_MODE`、`GF_DIAG_S3_SERVER_MS`、`GF_DIAG_TP_PERIOD_MS`、`GF_DIAG_SEC_PLUGIN`。

## 边界（明确不做）

- 真 A/B 分区 / RAUC 实刷 → **P3z**
- Classic DEM 全栈 / 完整 DTC 策略编辑器
- GMT 写回 `diag.yaml` / `ucm.yaml` / `collector.yaml`
- 把主机 SIL 延时表当成 ECU ASIL 证据

## 验收

- [x] DoIP TCP 会话 + NRC（`smoke_doip_ota.sh` / ctest doip|uds）
- [x] GMT OTA/UDS sheet：选包 / 进度日志 / 结果
- [x] 同页 DEM-lite（0x19/0x14）与 Collector 读环缓（0x31 F201）
- [x] 0x38（默认）与 0x34 可经 `ota_transfer.mode` 切换
- [x] UCM 编排 + 失败 Collector
- [ ] 真板 RAUC（P3z）
