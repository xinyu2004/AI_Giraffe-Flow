# DLT 实现计划（Giraffe Flow / AP lite）

> 状态：**完成**（SIL/GMT/配置）；真板仅部署手验。  
> 关联：[AP_LITE_BACKLOG.md](AP_LITE_BACKLOG.md)（**BL-DLT** · **BL-MEM-BOUND**）· [ROADMAP.md](ROADMAP.md) · `middleware/log` · `dep-manifest/`

## 1. 目标

- `gf_ara::log` → **COVESA DLT** 后端（标准协议）；上位机用 **dlt-viewer / dlt-receive** 或 **GMT DLT 客户端** 均可。
- **不强制客户用 GMT**；GMT 解析同一套标准 DLT。
- **SIL = HIL = 交叉**：源码编译进树（`third_party` / `.deps-prefix`），**禁止** apt 充当产品依赖。
- 有界内存（与 BL-MEM-BOUND 同审）：禁止无界环缓增长；满则丢。
- **不做**：DoIP 拉日志环、Live 旁路传日志、GMT 读板端 log 文件。

## 2. 架构

```text
App / EM / runtime  →  gf_ara::log  →  libdlt (client)
                              ↓
                     dlt-daemon（板上/SIL，有界缓冲）
                              ↓  TCP（默认 3490）或串口
              dlt-viewer | dlt-receive | GMT（可选）
```

| 通道 | 日志？ | 职责 |
|------|--------|------|
| **DLT** | **是（唯一上位机正统路径）** | bring-up / 模块 Info·Warn·Error |
| DoIP | 否 | UDS / OTA / DEM / Collector |
| Live | 否 | 信号观测 |
| console / file | 仅本机调试 | SIL 终端与落盘；GMT 不读文件 |

`gmt_export`：**已删除**（无 API / 无 drain / 无配置字段）；上位机只走 DLT。

## 3. 依赖与构建

| 项 | 约定 |
|----|------|
| 上游 | [COVESA/dlt-daemon](https://github.com/COVESA/dlt-daemon)（含 **libdlt** + **dlt-daemon**） |
| 集成 | `dep-manifest` pin → 源码 staging / `add_subdirectory`（同 iceoryx） |
| 体积（数量级） | `libdlt` ~百 KB；daemon 同量级；合计多半 &lt; 1 MB；viewer 不上板 |
| SKU | `sinks` 含 `dlt` 或 `GF_WITH_DLT` 时才链 libdlt / 打包 daemon |
| 主机工具 | `dlt-receive`（门禁）、可选系统/自编 `dlt-viewer`（不上板） |

## 4. 配置（log.yaml + gf-config）

与现有 **default_level / contexts** **正交**，不冲突：

| 维度 | 含义 | 配置 |
|------|------|------|
| 滤什么 | level + context | 已有 |
| 送到哪 | sinks | **新增** UI/字段 |

建议形态：

```yaml
default_level: INFO
sinks:
  - console    # stdout/stderr
  - dlt        # remote → daemon
  # - file
# file_path: ...          # 仅 file 开启
dlt:
  app_id: GFAP            # 4 字符；可 per-process 覆盖
contexts:
  - id: runtime
    level: INFO
    # dlt_ctx_id: RUNT    # 可选；默认由 id 映射
```

gf-config 页 2「日志」：在级别表下增加 **Sinks 勾选（console / file / DLT）**；勾 file 再露 path/上限；勾 DLT 再露 app_id。页 1 live/record 仍与日志分开。

## 5. 波次（GMT 可进第一波）

### D0 — 合同 ✅
- `DEPENDENCIES.yaml`：`dlt_daemon` → runtime_board；`versions.lock` pin **v2.18.11**。
- 本文档 + backlog **BL-DLT = in_progress**。

### D1 — 板上通路 + 标准客户端（GMT 客户端可同波） ✅
1. ✅ `bootstrap_deps.sh` 拉取 `middleware/third_party/dlt-daemon`；CMake `add_subdirectory` 编 `libdlt` + `dlt-daemon` + `dlt-receive`。
2. ✅ Host/`run_sil`：当 **gf-config/`log.yaml` sinks 含 `dlt`** 时 RouDi 前拉起自编 `dlt-daemon`（无 `GF_DLT=0` 开关）。
3. ✅ `gf_ara::log`：sink `dlt`（`DltSink`）；无 `/tmp/dlt` 时不 `register`（避免 ~10s 阻塞）；`GF_DLT_APP_ID` 仅 per-process APP ID。
4. ✅ 门禁手验：`dlt-receive` 见 `Offer→Running`；`gf_log_smoke` 无 daemon 也秒过。
5. ✅ **GMT**：Logging Tab = DLT TCP 客户端（`gf_gmt.dlt_client` 解析 v1）；**不**读 log 文件；亦可用 dlt-viewer。

### D2 — Bring-up 全覆盖 ✅
- Host：`gf_dlt_log` + `host_info`；EM / runtime / sm / exec / phm → `Logger` → DLT。
- APP ID（SIL）：`HOST` · `GATE` · `FCM_` · `USS_` · `PLAN`（`GF_DLT_APP_ID` / `gf_dlt_log -a`）。
- 启动顺序：`run_sil` / systemd → **EM** →（按需）`dlt-daemon` / RouDi → SOA apps；Host Info 日志经 `gf_dlt_log`（APP ID=`HOST`）。

### D3 — 硬化与收尾 ✅
- ✅ 删除 `gmt_export` / `DrainGmtExport`（代码与配置均无残留）。
- ✅ gf-config sinks UI；log 侧有界（DltSink ≤64 ctx；GMT pending 队列有上限）。
- ☐ 真板：rootfs 带上 daemon + libdlt 做一次通路手验（非功能缺口，属部署验证）。

## 6. 验收门禁

1. SIL：自编 daemon 起 → `run_sil` → **`dlt-receive`/`dlt-viewer`** 见 host/runtime/exec/sm/phm Info。
2. 无 daemon：应用不崩，降级 console，有 Warn。
3. GMT（若启用）：填 Host:Port 连 daemon，同序日志；无共享文件系统仍可用。
4. DoIP / Live 回归不受影响；GMT **无**读 `giraffe_modules.log` 的产品路径。

## 7. 明确不做 / 已撤销

- ~~GMT Logging 读 `runtime/logs/*.log`~~（已删除面板）。
- ~~DoIP 拉 `DrainGmtExport`~~。
- ~~Live 旁路传日志~~。
- ~~SIL 用 apt 安装 dlt-* 充当集成~~。
