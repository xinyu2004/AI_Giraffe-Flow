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
- **功能验收** = gf-config → compose → `compile_sil` → **`run_sil`**。  
  smoke = CI / 模块验证；可用 `GF_EM_USE_YAML` / `GF_PLATFORM_USE_YAML` 读 YAML。

## 启动 / EM

```text
systemd/init 或 run_sil
  → 只起 gf_em_daemon
  → LoadFromDeployConfig + ConfigureFromGenerated(log)
  → Spawn daemons + SOA apps
```

- 平台 daemon 陈旧回收在 **EM StartAll 之前**（dlt + RouDi + IPC）。
- `generated/em_launch.yaml` / `exec.yaml` = **人读 dump**。

### EM 管什么 / 不管什么

| EM **管** | EM **不管**（Flow / 主机工具） |
|-----------|--------------------------------|
| platform daemons + SOA apps | tap / Foxglove / inject / carla_bridge / DoIP server |

## 白名单（可 JSON）

| 机制 | 控制什么 |
|------|----------|
| `observability.json` **services** | live_tap / record 服务名 |
| collector `sources:` | 事件源过滤 |

## 行为（编译期 hpp）

| 机制 | 状态 |
|------|------|
| `deploy_config.hpp`（EM 开关 + `kEmLaunch[]` + **DoIP 端口/时序/OTA**） | **已落地** |
| `frame_ingest_config.hpp` | **已落地** |
| `log_config.hpp`（级别 / sinks / contexts / dlt app_id） | **已落地** |
| `platform_tables.hpp`（exec/phm；产品路径无 YAML 回退） | **已落地** |
| `iox_roudi.toml` | RouDi `-c`（上游需要） |

### Flow 调试

| 建议 | 做法 |
|------|------|
| **默认** | 读上述 hpp |
| **会话覆盖** | `GF_LIVE_TAP` / `GF_DOIP*` / `GF_FRAME_*` / `GF_INJECT_*` |
| **勿再加** | `*.env` / 板端可变行为 yaml |

## 验收主路径

```text
gf-config → Verify/compose → compile_sil → bash …/run_sil.sh
```
