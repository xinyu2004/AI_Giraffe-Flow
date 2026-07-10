# 代码分层：静态 / 生成 / 手写

> 对应仓库现状（P0 轨 A + 轨 B）。上传与本地产物见 [projects/UPLOAD_CHECKLIST.md](../../projects/UPLOAD_CHECKLIST.md)。

Giraffe Flow 板端与工具链按三层分工，避免「业务改中间件、OEM 差异散落在 App」：

```text
手写输入（projects/）          静态平台（middleware/ …）
  hpp / DBC / wiring / req              core / com / bindings / osal
            \                              /
             \                            /
              v                          v
         gf-codegen compose → gf.sor.json（本地，不上传）
         gf-codegen generate → generated/（本地，不上传）
                              /
手写业务（apps/*/src） -------+--> 链接静态库 + include 生成头
                              \
                               RouDi / iceoryx 运行
```

---

## 1. 静态代码（平台仓维护，随仓上传）

与具体 OEM/车型无关，**不**由 codegen 生成。业务只依赖其公开 API。

| 路径 | 内容 |
|------|------|
| [`middleware/core/`](../../middleware/core/) | `gf_ara::core`：`Result` / `ErrorCode` |
| [`middleware/com/`](../../middleware/com/) | `gf_ara::com`：`ServicePath`、Loopback Event |
| [`middleware/bindings/`](../../middleware/bindings/) | 传输插件；P0 为 [`iceoryx/`](../../middleware/bindings/iceoryx/) |
| [`middleware/osal/`](../../middleware/osal/) | `gf::osal`：单调时钟、sleep |
| [`cmake/`](../../cmake/)、[`scripts/bootstrap_deps.sh`](../../scripts/bootstrap_deps.sh) | 构建与第三方源码拉取 |
| [`tools/codegen/`](../../tools/codegen/) | 主机工具本身（Python；**不上板**） |
| [`schemas/`](../../schemas/) | SOR 契约 / 示例 |

对外命名空间示例：`gf_ara::com::binding::iceoryx::{InitRuntime, EventPublisher, EventSubscriber}`。

---

## 2. 动态代码（codegen 按项目生成，不上传）

由 **`gf-codegen`** 根据当前 project 的 SOR 生成，目录 gitignore，**每次本地/CI 现产**。

| 命令 | 产出 | 说明 |
|------|------|------|
| `compose --project …/project.yaml` | `projects/.../gf.sor.json` | 合并四类输入 |
| 同上 | `projects/.../reports/signal_lineage_report.yaml` | 连线/信号闭环检查（lineage） |
| `generate …/gf.sor.json --out …/generated/` | `include/gf_gen/types/*.hpp` | 结构体类型 |
| 同上 | `include/gf_gen/skeleton/*_skeleton.hpp` | **提供方**（publish / `Send`） |
| 同上 | `include/gf_gen/proxy/*_proxy.hpp` | **消费方**（subscribe / `Take`） |

`afc_with_uss` 一键路径（生成物落在**本项目**下）：

```bash
bash projects/oem_a/afc_with_uss/scripts/smoke_sil.sh
# → projects/oem_a/afc_with_uss/generated/
```

**lineage 报告：** 检查 DBC/hpp/wiring/req 合成后是否断连、是否有占位类型；给集成审阅与 CI 门禁用，**不是**板端运行文件。

---

## 3. 手写代码（工程师维护，随仓上传）

### 3.1 集成输入（系统 / 集成工程师）— `projects/<oem>/<product>/`

| 文件 | 角色 |
|------|------|
| `interfaces/**/io_types.hpp` | 模块接口（外仓交付或本车型） |
| `oem/oem_import.dbc` + `oem_import.yaml` | OEM 信号与归属 |
| `integration/wiring.yaml` | provide/require、bindings、dataflows |
| `req.yaml` + `project.yaml` | SKU / 验收 / 索引 |

示例验收项目：[`projects/oem_a/afc_with_uss/`](../../projects/oem_a/afc_with_uss/)。

### 3.2 业务逻辑（应用工程师）— `apps/*/src`

进程里的循环、填数、何时 `Send`/`Take`：**手写**。  
类型与 Proxy/Skeleton 可来自生成物（`GF_USE_GENERATED=ON`）。

当前平台参考 App（后续可随 project 归属演进）：

- [`apps/simulators/uss_feed/`](../../apps/simulators/uss_feed/) — 发布 `UssZones`
- [`apps/demo_pipeline/`](../../apps/demo_pipeline/) — 订阅消费

项目侧脚本（手写、可上传）：[`projects/oem_a/afc_with_uss/scripts/smoke_sil.sh`](../../projects/oem_a/afc_with_uss/scripts/smoke_sil.sh)（另有 `compile_sil` / `run_sil` / `compile_hil`）。

---

## 4. 对照表（上传时）

| 类别 | 上传？ | 典型路径 |
|------|--------|----------|
| 静态平台 | **是** | `middleware/**`、`cmake/`、`tools/codegen/src` |
| 手写输入 / 业务 / 项目脚本 | **是** | `projects/**`（除工作产物）、`apps/**/src` |
| compose / generate / lineage 工作产物 | **否** | `**/gf.sor.json`、`**/generated/`、`**/reports/` |
| 本地构建与依赖检出 | **否** | `build/`、`middleware/.deps-prefix/`、`middleware/third_party/*/`、`.venv/` |

更细的清单：[UPLOAD_CHECKLIST.md](../../projects/UPLOAD_CHECKLIST.md)。
