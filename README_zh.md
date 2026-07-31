# AI Giraffe Flow

**Lightweight middleware + toolchain for cross-platform SOA systems.**

面向跨平台 SOA：桌面先跑通，嵌入式 **ARM Linux** 优先（OSAL 预留 MIPS / RISC-V）。中间件提供可裁剪的 `gf_ara::*` 运行时与传输绑定；工具链一侧用 **gf-config** 把车型契约编进 SOR/代码生成，另一侧用 **GMT** 把联调从「盯日志猜时序」变成可 scrub、可回灌、可对接 Foxglove 的闭环——核心仍是板上/SIL 里真正跑着的 **Giraffe 模块**。

**English:** [README.md](README.md)

---

## 总览

| # | 主线 | 角色 | 深入 |
|---|------|------|------|
| **1** | **gf-config** | 工具链 · 配置侧 | [tools/gf-config](tools/gf-config/README_zh.md) · [SOR](docs/zh/architecture/sor-authoring.md) |
| **2** | **Giraffe 模块** | **产品主体** · 运行时、进程、**FuSa 证据** | [middleware](middleware/README.md) · [fusa/](fusa/README.md) · [设计](docs/zh/architecture/DESIGN.md) |
| **3** | **GMT** | 工具链 · 观测侧 | [tools/gmt](tools/gmt/README_zh.md) · [可观测演示](docs/zh/operations/OBSERVABILITY_DEMO.md) |

![架构：gf-config → Giraffe 模块（含 FuSa）→ GMT](result_pic/architecture_flow_zh.gif)

---

### 1. gf-config（配置侧工具链）

定 **要什么能力、谁连谁、板端裁哪些模块**，不实现算法。两页写回三层资产：

| 页 | 写什么 | 产物 |
|----|--------|------|
| **1 · 信号与应用** | 薄 SKU（`req.yaml`）+ 信号图画布（`wiring.yaml`） | deployments / dataflows / live_tap |
| **2 · 平台运行时** | `runtime_modules` + `platform/*`（exec · **EM 启动表** · PHM · Collector · diag · log · ucm；**per/tsync** 可勾选裁剪） | `platform_manifest` → CMake 裁剪 / EM 拓扑 |

- **Verify / Generate** → SOR + Proxy/Skeleton + lineage（含 `platform_em_launch` 等门禁）

![gf-config — 信号图（页 1）](result_pic/gf-config.png)

```bash
gf-config projects/oem_a/afc_with_uss/project.yaml
```

细节：[tools/gf-config/README_zh.md](tools/gf-config/README_zh.md) · [WORKFLOW](docs/zh/operations/WORKFLOW.md)

---

### 2. Giraffe 模块（主体）

这里是交付到板端、在 SIL 里真正跑起来的部分。业务算法可外仓替换；本仓提供 **可裁剪平台 + 参考进程**，用同一套 semantic 契约联调。

#### 2.1 分层

| 层 | 目录 | 做什么 |
|----|------|--------|
| **API / 运行时** | `middleware/` | `gf_ara::*` 对外；`gf::*` 对内；按 SKU `runtime_modules` 裁剪 |
| **传输插件** | `middleware/bindings/` | iceoryx（机内）、SOME/IP、DDS、cross_domain_ipc（MCU） |
| **执行与健康** | exec（**EM daemon**）/ phm / sm / collector | 拓扑拉起、relaunch、心跳、FG、事件收集 |
| **可移植** | `osal/` · `hal/` | 时钟 / 线程 / **进程 Spawn**；主目标 ARM Linux |
| **参考 App** | `apps/` | gateway、感知/超声/规划 stub、观测工具——**非量产算法** |
| **集成工程** | `projects/` | OEM 的 DBC / wiring / hpp / SIL·HIL 脚本 |
| **FuSa 证据** | `fusa/` | cases / metrics / Safety Case 骨架（通向完整 Safety Case，**非证书**） |

公开约定：**业务只依赖 semantic 服务名**；OEM 差异收在 adapter/gateway。详见 [DESIGN](docs/zh/architecture/DESIGN.md)。

#### 2.2 中间件包（按需裁剪）

与架构 GIF 中 Giraffe SoC 芯片对齐（`com` · `EM`∈exec · `exec` · `phm` · `sm` · `collector` · `OSAL` · `diag` · `ucm` · `log` · `per` · `tsync`）。

| 包 | 作用 |
|----|------|
| [com](middleware/com/) | 统一通信抽象（Proxy / Skeleton） |
| [bindings/iceoryx](middleware/bindings/iceoryx/) 等 | 传输后端 |
| [exec](middleware/exec/) | ExecutionClient + **EmDaemon**（OSAL Spawn；GIF 中 `EM`） |
| [phm](middleware/phm/) / [sm](middleware/sm/) / [collector](middleware/collector/) | 健康 / FG / 事件收集 |
| [osal](middleware/osal/) | OS 抽象（含 process；GIF 中 `OSAL`） |
| [diag](middleware/diag/) / [ucm](middleware/ucm/) | DoIP 会话 / OTA 编排（SIL） |
| [log](middleware/log/) | 日志 lite |
| [per](middleware/per/) / [tsync](middleware/tsync/) | 持久化 KV stub / 时间同步骨架（可裁剪） |
| [trace](middleware/trace/) | 时序 → VCD / GMT（偏 debug-path） |

总览：[middleware/README.md](middleware/README.md)

#### 2.3 参考进程与主链（示例 SKU）

以 [oem_a / afc_with_uss](projects/oem_a/afc_with_uss/) 为例：

```text
车态源（二选一）
  · gateway（continuous / 无回灌）  或  · inject（playhead，替 gateway）
        │
        ▼ EgoMotion
   ┌────┴────┬────────────┐
   ▼         ▼            ▼
  USS      FCM stub    （订 Ego 等）
   │         │
   ▼         ▼
 UssZones   Perception_Out
        \   /
         ▼
      planning → Trajectory
        │
        ▼
   tap → Foxglove / GMT Live
```

| 进程 | 角色 |
|------|------|
| `adapter.vehicle_can_gateway` | CAN/仿真 → EgoMotion、Perception_In…（回灌时关闭） |
| `sensing.uss` | Ego → UssZones |
| `perception.fcm` | Perception_In 或（回灌）Ego → 感知 stub |
| `planning.driving` | Ego（+ 可选感知/USS）→ Trajectory |
| `gf_iox_obs_tap` | 白名单服务 → NDJSON |
| `gf_iox_obs_inject` | playhead / continuous 回灌 Ego |

量产感知/规控在 **外部仓**；本仓 stub 证明契约与联调路径。见 [apps/](apps/README.md)。

#### 2.4 产品路径（SIL）

```bash
# 配置已 Verify / Generate 后：
bash projects/oem_a/afc_with_uss/scripts/compile_sil.sh

# 普通主链（gateway 开车态）
bash projects/oem_a/afc_with_uss/scripts/run_sil.sh

# 场景回灌（GMT playhead；全量 live 含 Ego → BEV）
GF_INJECT_MODE=playhead GF_INJECT_LIVE=all \
  bash projects/oem_a/afc_with_uss/scripts/run_sil.sh
```

脚本与环境变量：[projects/.../scripts/README.md](projects/oem_a/afc_with_uss/scripts/README.md)  
场景（变道→ACC→AEB）：[scenarios/README.md](projects/oem_a/afc_with_uss/scenarios/README.md)

#### 2.5 与工具链的边界

| Giraffe 模块负责 | 不负责（交给工具） |
|------------------|-------------------|
| 进程内算法与 I/O、iceoryx 上真发真收 | 画 wiring / 裁 SKU → gf-config |
| SIL 拉起 RouDi + App + tap/inject | Studio 布局、Tag、MCAP 分析 → GMT / Foxglove |
| semantic 契约在板上成立 | 离线改 DBC / lineage 会议替代 → compose |
| FuSa 证据（`fusa/`） | GMT 仍属 **debug-path**（不作板级 ASIL 证据） |

#### 2.6 FuSa（属于 Giraffe 模块）

通向 **完整 Safety Case** 的证据入口：L1/L2/L3、隔离、参考延时、Safety Case 骨架。入口：[fusa/](fusa/README.md)。

```bash
bash fusa/scripts/run_cases.sh
GF_FUSA_SIL=1 bash fusa/scripts/run_cases.sh
bash fusa/scripts/measure_latency.sh   # 可选：延时快照
```

---

### 3. GMT（观测侧工具链）

多进程 SIL 联调时，光看终端往往对不齐「谁在何时发了什么」。GMT 把同一条 tap 流接到本机时间轴与 Foxglove：**scrub / 倍速播放**对齐 DAG 与变量轨，**playhead 回灌**按帧把 Ego 灌进主链（gateway 关闭、无双发），需要时再 **Tag → MCAP**。端口少、和 `run_sil` 一条命令配合，日常「改完再看一眼」成本很低——**不替代模块，但让模块可被反复验证**。

![GMT — 变量轨 scrub / Live + Inject](result_pic/GMT.png)

| 端口 | 用途 |
|------|------|
| **8765** | Foxglove（模块 I/O → 可选合成 BEV） |
| **8766** | GMT Live（可选旁观） |
| **8767** | playhead 回灌 |

```bash
pip install -e tools/gmt -e 'tools/gmt[gui]'
GMT gui --project projects/oem_a/afc_with_uss \
  --session projects/oem_a/afc_with_uss/scenarios/overtake_acc_aeb.jsonl
```

细节：[tools/gmt/README_zh.md](tools/gmt/README_zh.md) · [OBSERVABILITY_DEMO](docs/zh/operations/OBSERVABILITY_DEMO.md)

---

## 仓库地图

| 目录 | 用途 |
|------|------|
| [middleware/](middleware/) | **Giraffe 运行时（主体）** |
| [apps/](apps/) | 参考 App / adapter / tap·inject |
| [projects/](projects/) | OEM 集成工程 |
| [fusa/](fusa/) | FuSa 证据（归属 Giraffe 模块） |
| [tools/gf-config/](tools/gf-config/) | gf-config |
| [tools/gf-codegen/](tools/gf-codegen/) | gf-codegen |
| [tools/gmt/](tools/gmt/) | GMT |
| [docs/zh/](docs/zh/README.md) | 文档索引 |

[STRUCTURE.md](STRUCTURE.md) · [ROADMAP](docs/zh/operations/ROADMAP.md)

## 许可证

[LICENSE](LICENSE)
