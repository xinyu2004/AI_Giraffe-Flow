# 配置运行期策略：白名单 vs 行为

> **English:** principles apply repo-wide; this doc is the source of truth.  
> 样板工程：`projects/afc/` · `afc/`。

## 原则

| 类别 | 可否运行期读 JSON/YAML | 人机入口 |
|------|------------------------|----------|
| **白名单 / 观测列表** | **可以** | gf-config → compose → `observability.json` |
| **行为轨迹**（EM Spawn、帧源、DoIP、Collector、bounds、ucm、DID…） | **不可以**依赖可变 YAML | gf-config → compose → **hpp 编进二进制** |
| **容量表**（RouDi TOML、bounds iceoryx） | 表数据；不是脚本开关 | compose → TOML / cmake |

- YAML 是 **作者存盘**（gf-config）；板端 / 产品路径 **不信任** 可变 yaml 作行为真相。
- **板端零行为 yaml**：stage **默认不拷** `platform/*.yaml`（`GF_STAGE_PLATFORM=1` 才拷）；产品 EM 只靠 `deploy_config.hpp`。
- **SIL 产品路径默认不设 `GF_PLATFORM_DIR`**（hpp-only）。smoke / verify 若需作者树，**显式** `export GF_PLATFORM_DIR=…/platform`。
- **无** `GF_PLATFORM_USE_YAML` / **无** `GF_EM_USE_YAML` 政策开关。EM YAML 仅当显式 `--launch` 或 `GF_EM_LAUNCH`。
- **runtime 自包含**：stage 后整树可拷到板端；禁止依赖 repo 外路径 / `carla_scenarios` import。
- **板端零 Python（运行时）**：板端 `runtime/` / EM / GMT 依赖树 **不得**依赖 Python 解释器或 `.py` 模块。  
  `frame_ingest` 在板端仅 C++（ISP 等）；`carla` / `colorbar` / `replay` 的 Python 桥 **仅 SIL 主机**。见 backlog `BL-BOARD-NO-PY`。
- **功能验收** = gf-config **Verify（+ 需要时 Generate）** → `compile_*` → **`run_*`**。  
  `compile_*` / `run_*` **不再**自动 compose。
  **板端产品入口**：`systemd` / `init.d` → `gf_em_daemon`（见 [`common/deploy/`](../../../common/deploy/)）。

## 行为（编译期 hpp）— 已落地

| 机制 | 产物 | 消费者 |
|------|------|--------|
| EM 启动表 + DoIP/UDS/OTA 常量 | `deploy_config.hpp` | `gf_em_daemon` · `gf_doip_ota_server` |
| exec / phm 表 | `platform_tables.hpp` | `process_bringup` |
| log | `log_config.hpp` | Logger / EM |
| frame_ingest | `frame_ingest_config.hpp` | ingest / FCM / gateway |
| **Collector（含 sources / dtc_map）** | `collector_config.hpp` | bringup · DoIP |
| **bounds（com/per/dlt/diag DID）** | `bounds_config.hpp` | bringup · DoIP |
| **ucm** | `ucm_config.hpp` | DoIP / UCM |
| **diag DID 种子** | `diag_seed.hpp` | DoIP |
| iceoryx RouDi | `iox_roudi.toml` + `iox_mgmt.cmake` | RouDi / CMake |
| 人读 dump | `generated/em_launch.yaml` · `exec.yaml` | **仅 diff**；产品 EM 忽略 |

改作者 yaml 后必须 **Verify(+Generate) → rebuild**；不 Generate 的二进制行为不变。

## 白名单（可 JSON）

| 机制 | 控制什么 |
|------|----------|
| `observability.json` **services** | live_tap / record 服务名 |

（Collector `sources:` 已进 hpp，不再当运行期 JSON 白名单。）

## 主机调试双轨（允许的 `GF_*`）

| 类 | 例子 | 说明 |
|----|------|------|
| 路径 | `GF_BUILD_DIR` · `GF_PER_DIR` · `GF_COLLECTOR_STORE` · `GF_LOG_*` | 主机落盘位置 |
| Flow / GMT | `GF_LIVE_TAP` · `GF_INJECT_*` · `GF_WS_*` · `GF_GMT_DEPEND` | 不上板 |
| 帧源 SIL 覆盖 | `GF_FRAME_SOURCE` · `GF_CARLA_*` | 覆盖 freeze 默认；板端仍读 hpp |
| DoIP 主机覆盖 | `GF_DOIP_*` · `GF_DIAG_*` · `GF_OTA_*` | 默认读 `deploy_config.hpp` |
| 故障注入 | `GF_PHM_FAULT_*` | 产品必须为 0 / 未设 |
| smoke 作者树 | **`GF_PLATFORM_DIR`**（显式） | **后期删除**（[BL-CFG-YAML-FALLBACK](AP_LITE_BACKLOG.md)）：今日仅当对应 freeze 头未编入时 YAML 回落 |

**勿再加** `*.env` / 板端可变行为 yaml。

## 已知缺口（后期）

| ID | 说明 |
|----|------|
| BL-CFG-YAML-FALLBACK | bringup/DoIP 仍保留「无 `GF_HAS_*` 头 + 显式 `GF_PLATFORM_DIR` → yaml」；SKU 产品路径应强制头齐全后删回落 |
| BL-IOX-SHM-USED | iceoryx SHM 预算/报告今日偏 **allocated / RouDi reserve**，非运行期 **used**；见 `mem_budget.py` FORMULAS |

## 启动 / EM

```text
systemd/init（产品）或 giraffe_launch（调试）/ run_sil
  → 只起 gf_em_daemon（LoadFromDeployConfig）
  → Spawn daemons + SOA apps
  → （主机）可选 GMT_depend：Foxglove / inject / DoIP
```

| EM **管** | EM **不管** |
|-----------|-------------|
| platform daemons + SOA apps + 可选 frame_ingest | tap / Foxglove / inject / DoIP server / carla_scenarios |

异常退出策略：不可 relaunch → EM 停整机；板端靠 systemd `Restart=on-failure`。

## 验收主路径

```text
gf-config Verify(+Generate) → compile_sil → bash …/run_sil.sh
# 板端：拷 runtime/ → systemctl enable --now giraffe-em
# smoke 显式作者树（可选）：
#   GF_PLATFORM_DIR=projects/afc/platform bash …/verify/smoke_….sh
```
