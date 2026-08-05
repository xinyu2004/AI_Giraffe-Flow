# P2.5 计划 — 主机工具链可配 + 架构师可视化起步

> 配套：[ROADMAP.md](ROADMAP.md) · [P2_PLAN.md](P2_PLAN.md) · [P2_REVIEW_CHECKLIST.md](P2_REVIEW_CHECKLIST.md) · [WORKFLOW.md](WORKFLOW.md) · [architect-tools.md](../architecture/architect-tools.md)  
> **状态（2026-07-24）：** P2.5 A/B/C 尖刺已落地 — SIL 编译器可换；**设计期真图 = B 画布**；**GMT GUI**（回放 + 先后/竞态 + 动画 DAG + live 跟随 + 标记 Tag）；**JSONL→VCD**（GTKWave）。

---

## 0. 定位

| | P2（已齐） | **P2.5（本阶段）** | P3 |
|--|-----------|-------------------|-----|
| 焦点 | 真可跑 SIL + 可观测 + gf-config A/B/C | **主机工具链可配** + **架构师可视化起步** | 真板 / 台架 / 多架构 soak |
| 不碰 | — | 不改 wiring/req 产品语义；DAG/GTKWave **不上车** | — |

**原则（与四脚本一致）：**

- SIL ≈ HIL：同一份 gf-config；差别是 **主机编译器** vs **交叉工具链** vs **部署**。
- 编译器 / toolchain **不是车型契约** → 不进 `req.yaml`；用环境变量 + 可选 CMake toolchain 文件。
- GMT / DAG / GTKWave = **上位机只读**；配置仍只经 gf-config。

```text
用户配置 CC/CXX 或 toolchain
        │
        ├─ compile_sil  → projects/.../build-sil/（或 GF_BUILD_DIR）
        └─ compile_hil  → projects/.../build-hil/（已有 GF_CROSS_*）

gf-config B 画布 = 设计期拓扑真图
gf-config 导出 .dot/SVG（可选附件）
session JSONL ──► GMT gui（录制 / 可编辑 Tag / 回放 + 先后/动画 DAG）
session JSONL ──► gf_iox_obs_inject（G3 闭环；替 gateway，禁止双发布）
session JSONL/MCAP ──► VCD ──► GTKWave（只读；`GMT measure export --format vcd`）
```

**工具顺序铁律：** `gf-config 编写 → codegen/compile → run → GMT 调试可视化`。  
主机 scrub **不**反转 iceoryx；闭环回灌用独立 inject **替换**边界发布方。

---

## 1. 轨 A — SIL 主机编译器可换

### 1.1 现状（落地后）

- `compile_sil.sh` / `_common.sh`：支持 `GF_CC`/`GF_CXX`/`GF_SIL_TOOLCHAIN_FILE`/`GF_BUILD_DIR`。
- `compile_hil.sh`：已有 `GF_CROSS_PREFIX` / `GF_TOOLCHAIN_FILE`。
- `bootstrap_deps.sh`：主机侧尊重 `GF_CC`/`GF_CXX`/`GF_DEPS_PREFIX`。

### 1.2 目标

用户可指定 **GCC / Clang / 其它** 编 SIL，风格与 HIL 对齐。

### 1.3 接口（冻结）

| 变量 | 含义 | 示例 |
|------|------|------|
| `GF_CC` / `GF_CXX` | 主机 C/C++ 编译器 | `clang` / `clang++` |
| `GF_SIL_TOOLCHAIN_FILE` | 可选完整 toolchain.cmake | `cmake/toolchains/host-clang.cmake` |
| `GF_BUILD_DIR` | SIL 输出目录（已有） | 默认 `projects/.../build-sil/`；换编译器可用独立目录避免混用 |
| `GF_DEPS_PREFIX`（可选） | 依赖安装前缀隔离 | 换编译器时避免与 GCC 的 iceoryx 混链 |

`compile_sil` 行为：

1. 若设 `GF_SIL_TOOLCHAIN_FILE` → `-DCMAKE_TOOLCHAIN_FILE=…`
2. 否则若设 `GF_CC`/`GF_CXX` → `-DCMAKE_C_COMPILER` / `-DCMAKE_CXX_COMPILER`
3. 否则保持系统默认（多为 GCC）

`bootstrap_deps.sh` 主机路径同样尊重 `GF_CC`/`GF_CXX`（文档写清：换编译器需重 bootstrap 或换 `GF_DEPS_PREFIX`）。

### 1.4 交付与验收

- [x] `compile_sil` + `_common` 读上述变量；示例 `cmake/toolchains/host-clang.cmake`
- [x] project / 仓 README 给 Clang 示例一行
- [ ] 验收：`GF_CXX=clang++ GF_BUILD_DIR=…/build-clang` 能编过冒烟（至少 ctest 主路径）

**不做：** gf-config GUI 里选编译器（可本阶段末或 P3 再挂）；为每种编译器强制多份 deps（先文档约定隔离）。

---

## 2. 轨 B — 设计期拓扑 vs GMT 运行可视化

### 2.1 边界（2026-07-23 定案）

| 能力 | 落点 | 说明 |
|------|------|------|
| 设计期真图 | **gf-config B 画布** | 可编辑 wiring；不再另开「DAG」页 |
| Graphviz 附件 | gf-config 导出 `.dot`/SVG；或 `GMT architect dag --format dot` | 需本机 `dot` 才能出 SVG |
| 回放时间轴 | **GMT GUI** | 与 live/session 绑定 |
| 先后 / 竞态 | **GMT GUI**（默认可优先） | 事件表 + Δt；日常调试常用 |
| 动画 DAG | **GMT GUI** | 同一时间轴点亮边 |
| Lineage | gf-config B 右侧 + `GMT architect lineage` | Verify 门禁，不是运行可视化 |

### 2.2 阶段

| 阶段 | 内容 | 验收 |
|------|------|------|
| **B0** | 规格与分工写清（本文 + architect-tools） | ✅ |
| **B1** | CLI `GMT architect dag --format json\|mermaid\|dot`（CI/导出） | ✅ |
| **B2** | ~~gf-config 嵌 DAG 页~~ → **改为**：去掉独立 DAG 页；**导出 .dot/SVG** | ✅ |
| **B3** | **GMT GUI**：时间轴 + 先后/竞态 + 动画 DAG + 录制/标记·片段 Tag/MCAP/VCD/Foxglove/live 跟随 | `GMT gui` ✅ |
| **B4** | G2 tap NDJSON→session；G3 `iox_obs_inject`（B1+B2） | ✅ smoke_sil_inject / smoke_sil_inject_b2 |

**铁律：** 不以手绘 PPT 为通信真相；运行动画必须有时间轴（回放或 live）。

---

## 3. 轨 C — GTKWave 路径

### 3.1 定位

Host-only 时序/波形；与 **Foxglove**（语义 topic 实时）互补，**不替代** live WS。

设计文档已写：统一 trace + VCD/FST → GTKWave（见 DESIGN / WORKFLOW）。

### 3.2 阶段

| 阶段 | 内容 | 验收 |
|------|------|------|
| **C0** | 规格：导出源优先 **session JSONL / tagged**；粒度先「服务 + 少量数值字段」非整 DBC | 本文 §3.3 ✅ |
| **C1** | Spike：`GMT measure export --format vcd` 从 session JSONL 出 VCD | ✅ `smoke_gmt_vcd`；`gtkwave` 可选打开 |
| **C2** | 文档：Foxglove 看语义 / GTKWave 看时序；挂 OBSERVABILITY 附录 | ✅ OBSERVABILITY_DEMO §5.1 |
| **C3**（可延后） | 菜单一键唤起 GTKWave 进程；FST；更多字段 | GUI 已能导出 VCD；唤起进程可后补 |

**不做（P2.5）：** 车端装 GTKWave；全 DBC 逐 bit；替代 Foxglove live。

### 3.3 C0 规格（冻结草案）

| 项 | 约定 |
|----|------|
| 输入 | 优先 `session.jsonl` / `session_tagged.jsonl`（GMT measure record/tag 产出）；MCAP 可后接 |
| 输出 | IEEE 1364 VCD（`.vcd`）；先不写 FST |
| CLI（C1） | `GMT measure export --format vcd --in …jsonl --out …vcd`（与现有 MCAP export 并列） |
| 轨命名 | `gf.<service_short>.<field>`，例如 `gf.EgoMotion.seq` |
| 字段选取 | 默认：整型/浮点标量 + `t_ns`；忽略嵌套对象 / 大数组；未知类型跳过并 warn |
| 时间轴 | 用行内 `t_ns`（或 `log_time_ns`）→ VCD timescale `1ns`；缺时间则按行号递增 |
| 与 Foxglove | Foxglove = 语义 topic 实时；GTKWave = 离线时序/对齐；同一 session 可双看 |

**C1 最小验收场景：** `tools/gmt/fixtures/session_stub.jsonl`（或 tagged）→ VCD → `gtkwave` 至少 1 条数值轨。

---

## 4. HIL / 部署（同阶段只规划）

| 项 | P2.5 态度 |
|----|-----------|
| 交叉工具链 | 已有 `GF_CROSS_*`；与 SIL `GF_CC`/`GF_CXX` 写成同一「工具链配置」表 |
| 板端部署 | 接口草案：`build-hil` 打包、ssh/scp、起 RouDi+进程；**实现可标 P2.5-H 或并入 P3**，不挡 A/B/C |

---

## 5. 目录与脚本（提醒）

| 用途 | 路径 |
|------|------|
| 生成物 | `projects/<oem>/<sku>/generated/` |
| SIL 二进制 | `projects/<oem>/<sku>/build-sil/`（或 `GF_BUILD_DIR`） |
| HIL 二进制 | `projects/<oem>/<sku>/build-hil/`（或 `GF_BUILD_DIR_HIL`） |
| 观测落盘 | `${BUILD}/observability/`（session/MCAP）；`${BUILD}/runtime/{logs,collector,per}` |
| 产品脚本 | 仅 `compile_sil\|hil` + `run_sil\|hil` |
| 验证 | `scripts/verify/` |

---

## 6. 节奏（约 2～3 周）

| 周 | 重点 |
|----|------|
| W1 | 本文冻结；轨 A 落地 + ROADMAP 切到 P2.5 |
| W2 | B1 CLI dot；C0 规格；边界定案（无 gf-config DAG 页） |
| W3 | B2 导出 Graphviz；B3 GMT GUI MVP；C1 VCD（可并行） |

---

## 7. 明确不做（P2.5）

- 改产品 wiring/req 语义；把 DAG/GTKWave 编进量产镜像  
- 真 MCU / DoIP 台架 / 量产 OTA（P3）  
- ISO 26262 认证话术  
- 用 GTKWave 替代 Foxglove live  

---

## 8. 关门验收

- [x] SIL：文档化的 GCC/Clang（或自定义）路径可编过冒烟（`scripts/README` · `host-clang.cmake` · `GF_CC`/`GF_CXX`/`GF_SIL_TOOLCHAIN_FILE`）  
- [x] 设计期：B 画布为真图；gf-config 可导出 .dot/SVG；无独立 DAG 页  
- [x] GMT GUI：回放时间轴 + 先后/竞态 + 动画 DAG + 录制/可编辑 Tag + live 跟随（`GMT gui`）  
- [x] G3 B1：`gf_iox_obs_inject` + `GF_INJECT_SESSION` run_sil（smoke_sil_inject）  
- [x] G3 B2：`GF_INJECT_DUT` / `GF_INJECT_APPS` 子集启动（smoke_sil_inject_b2）  
- [x] GTKWave：JSONL→VCD 尖刺可复现（`smoke_gmt_vcd`；本机可选 `gtkwave`）  
- [x] ROADMAP：当前阶段 = P2.5；边界写清（形式 Review 勾选可并行）  

---

## 9. 开工检查清单

- [x] P2 Review：功能路径已验证；形式勾选清单可并行收口（见 [P2_REVIEW_CHECKLIST.md](P2_REVIEW_CHECKLIST.md)）  
- [x] 冻结本文 §1.3 / §2 / §3.2  
- [x] W1：改 `compile_sil` 编译器开关；补 `host-clang.cmake`
- [x] W2：B1 `architect dag --format mermaid|dot`；C0 规格；边界定案  
- [x] W3：去掉 gf-config DAG 页；导出 Graphviz；GMT GUI MVP；C1 VCD  
