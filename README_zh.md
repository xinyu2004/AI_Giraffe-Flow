# AI Giraffe Flow（中文）

**面向跨平台 SOA 的轻量中间件 + 工具链**：台式机上先跑通，嵌入式优先落地；借鉴 AUTOSAR Adaptive 的有用思想，**不必购买完整商业 AP 工具链**。

**English:** [README.md](README.md)

> 当前状态：**架构 + monorepo 骨架**（文档与目录已齐；**尚无运行时/工具实现代码**）。

仓库地图与依赖：[STRUCTURE.md](STRUCTURE.md) · [deps/README.md](deps/README.md)

---

## 为什么做

做感知 / 规划 / 控制 / IVI 的团队往往需要：进程与健康管理、SOA 通信、主机厂 ARXML/DBC 导入，同时要接 ROS 2、机内零拷贝、以及 pipeline 出问题时的深度观测。完整 Adaptive 工具链通常过重、过贵。

**Giraffe Flow** 的取舍是：只保留 AP 里真正好用的部分，做成可裁剪的工程平台，并自建「需求模型 → 代码生成 → 架构评审」闭环。

---

## 这个仓库是什么

一个 monorepo，计划包含：

| 部分 | 作用 |
|------|------|
| **运行时** | 执行 / 健康 / 状态 + `gf_ara::com`（语义贴近 ARA，扩展放在 `gf::*`） |
| **传输** | **iceoryx**（机内）、**SOME/IP**（车规 SOA）、**DDS**（ROS 2 / 跨 SoC） |
| **SOR 工具链** | OEM ARXML/DBC → **`gf.sor.json`** → 生成 Proxy/Skeleton 与 manifest |
| **上位机工具** | DAG 全图、信号扭转 review、GTKWave、录制回放 |

**SOR（Statement of Requirements）** 是本项目的**唯一需求/模型契约**：服务定义、部署、provides/requires 图、OEM 信号映射。Codegen 与架构工具都读同一份 SOR，保证「图上看到的」和「生成出来的 com」一致。

---

## 能帮到谁

| 角色 | 收益 |
|------|------|
| **中间件 / 平台** | OSAL + HAL + Binding 插件，跨 OS / SoC 移植 |
| **架构 / 集成** | DAG + 信号血缘；OEM 导入尽量不改编业务 |
| **感知 / 规控应用** | 稳定服务接口；车型差异沉在雷达等适配进程 |
| **算法 / ROS** | DDS 对接生态，少维护两套手搓栈 |

台式机优先调试，板端优先交付：同一套 SOR / manifest，用 profile 切换（`desktop` → `board` → `vehicle-debug` → `production`）。

---

## 构想一览

```text
OEM ARXML/DBC ──► Importer ──► gf.sor.json ──► Codegen ──► gf_ara::com + manifests
                                   │
                    DAG / 信号 Review（主机）     进程：雷达 | 感知 | 规划 | 控制 | IVI
                                   ▼
                    Runtime（EM/PHM）+ iceoryx | SOME/IP | DDS
```

已对齐的关键决策：

- 借鉴 AP（**exec / phm / com / sm / log**），重安全 / OTA 等后置  
- 对外 **`gf_ara::*`**，对内 **`gf::*`**  
- 服务可细、**进程按故障域**（雷达独立；IVI 可本机或另一 SoC）  
- 车速等共享信号经单一 gateway 一书多订  
- 平台 monorepo；客户车型工程另仓  

细节见：[设计文档](docs/zh/architecture/DESIGN.md) · [操作流程](docs/zh/operations/WORKFLOW.md)

---

## 仓库地图（骨架）

```text
schemas/      SOR 契约（gf.sor.schema.json）
middleware/   exec · phm · sm · com · log · trace
platform/     osal · hal
bindings/     iceoryx · someip · dds
tools/        importer · codegen · architect · record_replay · lint
apps/         radar · perception · planning · control · ivi · …
deploy/       profiles（desktop|board|vehicle-debug|production）
deps/         DEPENDENCIES.yaml + 版本锁（第三方库集中管理）
third_party/  上游检出（未钉扎前保持空）
docs/en|zh/   设计 · 流程 · 依赖说明
```

详见 [STRUCTURE.md](STRUCTURE.md)

## 文档

| 链接 | 内容 |
|------|------|
| [docs/zh/README.md](docs/zh/README.md) | 中文索引 |
| [docs/zh/architecture/DESIGN.md](docs/zh/architecture/DESIGN.md) | 设计 |
| [docs/zh/operations/WORKFLOW.md](docs/zh/operations/WORKFLOW.md) | 流程 |
| [docs/zh/dependencies/README.md](docs/zh/dependencies/README.md) | 第三方依赖 |
| [README.md](README.md) / [docs/en/](docs/en/README.md) | English |

## 路线图（极简）

0. 冻结 SOR 字段级 schema，评审矩阵 — **下一步再讨论从哪开工**  
1. 三 binding 通信 MVP  
2. 执行 + 健康管理  
3. ROS + 可观测（DAG / GTKWave / 录制回放）  
4. 嵌入式收敛 + 量产 profile  

## 许可证

见 [LICENSE](LICENSE)。
