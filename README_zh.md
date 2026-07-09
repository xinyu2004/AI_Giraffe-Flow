# AI Giraffe Flow（中文）

**轻量跨平台 SOA 中间件 + 工具链**：台式机先跑通，**嵌入式 ARM Linux** 优先；预留 MIPS / RISC-V。

**English:** [README.md](README.md)

> 状态：**架构 + 目录骨架**（含 `ucm`/`diag` 头文件占位；**P0 实现尚未开始**）。

[STRUCTURE.md](STRUCTURE.md) · [路线图 P0–P3](docs/zh/operations/ROADMAP.md) · [deps](deps/README.md)

---

## 为什么做

感知 / 规划 / 控制团队需要进程管理、SOA、OEM 导入、ROS 零拷贝与可观测性，但不必买下完整 AP 商业栈。

**Giraffe Flow**：可裁剪工程平台 + **SOR → gf-codegen → GMT** 闭环。

---

## 这个仓库是什么

| 部分 | 作用 |
|------|------|
| **运行时** | `gf_ara::com`、exec/phm/sm、**ucm（OTA）**、**diag（DoIP）** — 按 SKU 裁剪 |
| **传输** | iceoryx、SOME/IP、DDS；MCU 场景 **cross_domain_ipc** |
| **契约** | **`gf.sor.json`** — 唯一需求模型 |
| **gf-codegen** | `import` → `lint` → `generate` |
| **GMT** | 架构评审、度量、ROS 桥接（Foxglove 等） |

**不含**量产感知/规划源码 — 见 `apps/simulators/` 与外部仓。

---

## Vision：一条流水线

```text
OEM ──► gf-codegen import ──► gf.sor.json ──► lint ──► generate ──► 构建部署
                                                              │
                                         板端运行 ◄───────────┘
                                                              │
                                         GMT measure/bridge ◄──┘（上位机）
```

---

## 板端 vs 上位机

| | 板端 Onboard | 上位机 PC |
|---|--------------|-----------|
| runtime / bindings | ● | |
| adapters / sim / 外仓组件 | ● | |
| MCU（AUTOSAR CP，无 gf） | ● 可选 | |
| gf-codegen | | ● |
| GMT、Foxglove、PlotJuggler | | ● |
| 交叉编译与打包 | | ● |

`ap_mcu_cp` 时 AP 上另有 `mcu.cp_gateway`。详见 [DESIGN §8](docs/zh/architecture/DESIGN.md)。

---

## 目标硬件与解耦

- **主：** ARM Linux  
- **预留：** MIPS、RISC-V（`platform/osal/arch/`）  
- **原则：** SOR 唯一契约；middleware/bindings 插件化；业务与 OEM 差异在 adapter/gateway  

---

## 路线图

| 阶段 | 内容 |
|------|------|
| **P0** | SOR、codegen、iceoryx 双进程、ARM OSAL → [详情](docs/zh/operations/ROADMAP.md) |
| **P1** | 三 binding、GMT、ucm/diag stub、MCU gateway 模拟 |
| **P2** | MCAP/Tag/bench、证据包 |
| **P3** | 量产 profile、DoIP/OTA 台架、多架构 OSAL |

**下一步：** [P0 实施计划](docs/zh/operations/P0_PLAN.md)

---

## 仓库地图

见 [STRUCTURE.md](STRUCTURE.md)

## 文档

| 链接 | 内容 |
|------|------|
| [DESIGN.md](docs/zh/architecture/DESIGN.md) | 设计 |
| [ROADMAP.md](docs/zh/operations/ROADMAP.md) | P0–P3 |
| [THIRD_PARTY_EVALUATION.md](docs/zh/dependencies/THIRD_PARTY_EVALUATION.md) | 三方库评估 |
| [WORKFLOW.md](docs/zh/operations/WORKFLOW.md) | 流程 |

## 许可证

[LICENSE](LICENSE)
