# 配置运行期策略：白名单 vs 行为

> **English:** principles apply repo-wide; this doc is the source of truth.  
> 样板工程：`projects/oem_a/afc_no_uss/`。

## 原则

| 类别 | 可否运行期读 JSON/YAML | 人机入口 |
|------|------------------------|----------|
| **白名单 / 观测列表** | **可以** | gf-config → compose → `observability.json` |
| **行为轨迹**（EM Spawn、帧源、DoIP 参数、log…） | **不可以**依赖可变 YAML | gf-config → compose → **hpp 编进二进制** |
| **容量表**（RouDi TOML、bounds） | 表数据；不是脚本开关 | compose → TOML / cmake |

- YAML 是 **作者存盘**（gf-config）；板端 / 产品路径 **不信任** 可变 yaml 作行为真相。
- **板端零行为 yaml**：stage **默认不拷** `platform/*.yaml`（`GF_STAGE_PLATFORM=1` 才拷）；产品 EM 只靠 `deploy_config.hpp`。
- **runtime 自包含**：stage 后整树可拷到板端；禁止依赖 repo 外路径 / `carla_scenarios` import。
- **可选视频契约**（`frame_ingest`）：非 DAQ；客户可不配。配了则 → `frame_ingest_config.hpp` + `generated/camera_contract.json`（给 carla_scenarios 只读）。
- **CARLA SIL 文件旁路**（非 GfChannel）：默认在 **`projects/.../runtime_ipc/`**（禁止 `/tmp/gf_*`）。图像主路径仍是 GfChannel shm。
- **超时 / 卡死可见性**（已落地）：启动失败、子进程异常退出、帧超时至少打 `[ERROR]` / EM `log.Error`；异常且不可 relaunch → EM 停整机（见下节）。  
- **功能验收** = gf-config **Verify（+ 需要时 Generate）** → `compile_*` → **`run_*`**（默认挂 GMT_depend）。  
  `compile_*` / `run_*` **不再**自动 compose。
  **板端产品入口**：`systemd` / `init.d` → `gf_em_daemon`（见 [`common/deploy/`](../../../common/deploy/)）。`giraffe_launch` **仅调试**。

## 共用模板

见 [`common/README.md`](../../../common/README.md)：`bootstrap_sku_scripts.sh` **拷贝**模板到 SKU；之后 SKU 分叉，**不**长期 `source common/`。

## 启动 / EM

```text
systemd/init（产品）或 giraffe_launch（调试）/ run_sil
  → 只起 gf_em_daemon
  → LoadFromDeployConfig + ConfigureFromGenerated(log)
  → Spawn daemons + SOA apps（含可选 host.frame_ingest）
  → （主机调试）可选 GMT_depend：Foxglove / inject / DoIP
```

- 平台 daemon 陈旧回收在 **EM StartAll 之前**（dlt + RouDi + IPC）。
- `generated/em_launch.yaml` / `exec.yaml` = **人读 dump**。

### 异常退出与超时可见性

| 场景 | 行为 |
|------|------|
| 子进程异常退出且**不会** relaunch | EM `log.Error` + 子日志 tail → **`RequestShutdown` 停整机** |
| exit 75 且 `restart_enabled` | 按现有策略 relaunch |
| 板端恢复 | **systemd / init `Restart=on-failure`** 拉起整棵 EM 树（不是「死进程后继续跑别的」） |
| frame_ingest / carla_bridge 致命失败 | stderr 固定前缀 `[ERROR] …` → EM child log |
| FCM 帧超时 / 坏配置 | stderr `[ERROR] perception.fcm: …`（仍发 empty packet，不立刻杀进程） |
| PHM Alive | 进程心跳；**不是**统一 DAQ/帧卡死 watchdog |

不设会话环境开关控制「是否停机」；策略写死在 EM。

### EM 管什么 / 不管什么

| EM **管** | EM **不管**（GMT_depend / 主机工具） |
|-----------|--------------------------------------|
| platform daemons + SOA apps + 可选 frame_ingest | tap / Foxglove / inject / DoIP server / carla_scenarios |

## 白名单（可 JSON）

| 机制 | 控制什么 |
|------|----------|
| `observability.json` **services** | live_tap / record 服务名 |
| collector `sources:` | 事件源过滤 |

## 行为（编译期 hpp）

| 机制 | 状态 |
|------|------|
| `deploy_config.hpp`（EM 开关 + `kEmLaunch[]` + **DoIP**） | **已落地** |
| `frame_ingest_config.hpp`（可选视频契约 + mount + GfChannel 槽） | **已落地** |
| `camera_contract.json`（给场景机对齐；非板端行为真相） | **已落地** |
| `log_config.hpp` | **已落地** |
| `platform_tables.hpp` | **已落地** |
| `iox_roudi.toml` | RouDi `-c`（上游需要） |
| SIL file-IPC（`runtime_ipc/*`） | CARLA 旁路；**非** GfChannel；勿用 `/tmp/gf_*` |

### GfChannel

大块图像平面 shm（原内部代号 tip / TipChannel）。库：`libgf_channel.so`；槽名默认 `gf.channel.front`（短期兼容 `gf.tip.*`）。

Foxglove tip 相机（`/gf/camera/front/tip/compressed`）默认 **只读 Open 同一槽**；`runtime_ipc/front.yuv` 仅为 SIL 文件旁路（`GF_TIP_FRAME` / `tip_transport=file` / `GF_TIP_FILE_TEE=1`）。

### Flow 调试

| 建议 | 做法 |
|------|------|
| **默认** | 读上述 hpp |
| **会话覆盖** | `GF_LIVE_TAP` / `GF_DOIP*` / `GF_FRAME_*` / `GF_INJECT_*` |
| **勿再加** | `*.env` / 板端可变行为 yaml |

端口预检在 **GMT_depend**，不在 EM / `GF_GMT_DEPEND=0`。

## 验收主路径

```text
gf-config Verify(+Generate) → compile_sil → bash …/run_sil.sh
# 板端：拷 runtime/ → systemctl enable --now giraffe-em
# 调试：./runtime/bin/giraffe_launch
```
