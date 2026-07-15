# P1 完整 Review 清单

> 对应计划：[P1_PLAN.md](P1_PLAN.md) · 路线图：[ROADMAP.md](ROADMAP.md)  
> 用法：按 **R0 → R7** 顺序逐项过；每项勾选「通过 / 需改 / 延后」，并在备注栏写修改意图。  
> 前置：仓库根目录 · 已 `source .venv/bin/activate`（或 `PATH` 含 `.venv/bin`）· `pip install -e tools/codegen[dev] -e tools/gmt[dev]`

**整体判定（review 结束后填）：**

| 结论 | □ 通过可进 P2 | □ 有阻塞修改后再验收 | □ 部分延后 P2 |
|------|---------------|----------------------|---------------|
| Reviewer | | 日期 | |

---

## R0 — 总览与边界（先对齐预期）

| # | 检查项 | 期望 | 通过 | 需改 | 延后 | 备注 |
|---|--------|------|:----:|:----:|:----:|------|
| R0.1 | P1 范围理解 | 只编 `req.yaml`/`wiring.yaml`，不上板；无 IoNAS / 真 MCU / 真 DoIP / 完整 Foxglove | □ | □ | □ | |
| R0.2 | 工具边界 | **gf-config**=唯一作者 GUI；**gf-codegen**=compose/lint/generate/import；**GMT**=只读 architect + measure | □ | □ | □ | |
| R0.3 | 接口语言配对（§3.0b） | `.fidl`(+`.fdepl`)↔SOME/IP 路径；OMG `.idl`↔DDS；`req.bindings`=SKU 栈勾选（正交） | □ | □ | □ | |
| R0.4 | 明确不做清单 | P1_PLAN §5：不导出 fidl/fdepl；不把 fdepl 当 bindings；不做两套 DDS+完整 SOME/IP 同时量产级 | □ | □ | □ | |

**关键路径：** `docs/zh/operations/P1_PLAN.md` · `docs/zh/operations/ROADMAP.md`

---

## R1 — Cfg（gf-config A/B/C）

| # | 检查项 | 怎么验 | 通过 | 需改 | 延后 | 备注 |
|---|--------|--------|:----:|:----:|:----:|------|
| R1.1 | 打开项目可见连线 | `gf-config` 打开 `projects/oem_a/afc_with_uss`，B 页有进程卡与边 | □ | □ | □ | |
| R1.2 | A 页 req 完整 | capabilities / runtime_modules / bindings / apps / acceptance 可编辑并 Save → `req.yaml` | □ | □ | □ | |
| R1.3 | B 页拖线 / 删边 / 布局保持 | Out→In 连线；Delete；重建后位置不丢 | □ | □ | □ | |
| R1.4 | 导入 hpp | 「导入 hpp/h…」→ 勾选 struct → 写回 `modules[].hpp` + 端口 | □ | □ | □ | |
| R1.5 | 导入 fidl | 「导入 fidl…」→ 样例 `interfaces/demo_fidl/VehicleStatus.fidl` | □ | □ | □ | |
| R1.6 | 搜索 / 选中边 | 搜索框定位；实线与缺失虚线可选 | □ | □ | □ | |
| R1.7 | C 页 lineage | compose 后 C 页绿/红与报告一致 | □ | □ | □ | |
| R1.8 | 不写 SOR | GUI 只动 req/wiring，不手改 `gf.sor.json` | □ | □ | □ | |

**代码/文档：** `tools/config/` · `tools/config/README.md` · `tools/config/src/gf_config/gui/`

---

## R2 — F（CMake SKU 裁剪）

| # | 检查项 | 怎么验 | 通过 | 需改 | 延后 | 备注 |
|---|--------|--------|:----:|:----:|:----:|------|
| R2.1 | compose 产出 SKU cmake | `python -m gf_codegen.compose --project projects/oem_a/afc_with_uss/project.yaml` → `generated/gf_build.cmake` 含 `GF_WITH_*` / `GF_APPS` | □ | □ | □ | |
| R2.2 | GfModules 消费 | 存在 `cmake/GfModules.cmake`；configure 日志出现 binding/app | □ | □ | □ | |
| R2.3 | desktop_default | `-DGF_SKU_CMAKE=cmake/profiles/desktop_default.cmake` | □ | □ | □ | |
| R2.4 | desktop_minimal | 低配仅 demo；缺模块 STATUS skip 不炸 | □ | □ | □ | |
| R2.5 | 对照表 | `cmake/README.md` req↔CMake 表可读 | □ | □ | □ | |

**命令备忘：**

```bash
python -m gf_codegen.compose --project projects/oem_a/afc_with_uss/project.yaml
# 查看：projects/oem_a/afc_with_uss/generated/gf_build.cmake
```

---

## R3 — I（FIDL / FDEPL）

| # | 检查项 | 怎么验 | 通过 | 需改 | 延后 | 备注 |
|---|--------|--------|:----:|:----:|:----:|------|
| R3.1 | parse_fidl 单测 | `pytest tools/codegen/tests/test_parse_fidl.py -q` | □ | □ | □ | |
| R3.2 | 样例 fidl | `projects/oem_a/afc_with_uss/interfaces/demo_fidl/VehicleStatus.fidl` 候选含 VehiclePose / SpeedChanged 等 | □ | □ | □ | |
| R3.3 | GUI 导入写回 | Save 后 `wiring.modules[].fidl` + provides/requires | □ | □ | □ | |
| R3.4 | compose 合类型 | modules 挂 fidl 后 SOR types 有对应 struct | □ | □ | □ | |
| R3.5 | parse_fdepl | `pytest tools/codegen/tests/test_parse_fdepl.py -q`；样例 `.fdepl` ServiceID=0x1234 | □ | □ | □ | |
| R3.6 | 边界确认 | **不**导出 fidl/fdepl；fdepl **不**代替 `req.bindings` | □ | □ | □ | |

---

## R4 — M（MCU 桌面联调）

| # | 检查项 | 怎么验 | 通过 | 需改 | 延后 | 备注 |
|---|--------|--------|:----:|:----:|:----:|------|
| R4.1 | smoke 脚本 | `bash projects/oem_b/adc_full/scripts/smoke_mcu_desktop.sh` | □ | □ | □ | |
| R4.2 | 传输库 | `middleware/bindings/cross_domain_ipc` + `gf_cross_domain_ipc_smoke` | □ | □ | □ | |
| R4.3 | peer / gateway | `gf_cp_ipc_peer` ↔ `gf_mcu_cp_gateway`（CanInfo → TrajPlot/P_Parking） | □ | □ | □ | |
| R4.4 | profile | `cmake/profiles/mcu_desktop.cmake`（无 iceoryx） | □ | □ | □ | |
| R4.5 | 边界 | 无真 MCU / 无 AUTOSAR CP 代码；仅桌面 Unix socket | □ | □ | □ | |

---

## R5 — E / U（exec · phm · ucm · diag）

| # | 检查项 | 怎么验 | 通过 | 需改 | 延后 | 备注 |
|---|--------|--------|:----:|:----:|:----:|------|
| R5.1 | 一键 smoke | `bash scripts/smoke_eu_stub.sh` | □ | □ | □ | |
| R5.2 | exec | `gf_exec_smoke`：Offer → Running | □ | □ | □ | |
| R5.3 | phm Alive/Deadline | `gf_phm_alive_deadline_smoke`：超时 miss → Alive 恢复 → Pause | □ | □ | □ | |
| R5.4 | ucm 状态机 | Idle→Transfer→Process→Activate→Rollback | □ | □ | □ | |
| R5.5 | diag DoIP stub | Initialize / Shutdown / TesterPresent | □ | □ | □ | |
| R5.6 | 文档钩子 | ucm README 写明 OTA 时 PHM `SetPaused` | □ | □ | □ | |
| R5.7 | 边界 | 无真 OTA 后端 / 无真 DoIP 台架 | □ | □ | □ | |

---

## R6 — B / D（DDS · SOME/IP · IDL）

| # | 检查项 | 怎么验 | 通过 | 需改 | 延后 | 备注 |
|---|--------|--------|:----:|:----:|:----:|------|
| R6.1 | 一键 smoke | `bash scripts/smoke_bd_stub.sh` | □ | □ | □ | |
| R6.2 | DDS binding | `GF_WITH_DDS` → `gf_ara::com_dds`；默认厂商文档写 Cyclone；offline=stub | □ | □ | □ | |
| R6.3 | SOME/IP stub | `GF_WITH_SOMEIP` → `gf_ara::com_someip` Init/Shutdown | □ | □ | □ | |
| R6.4 | emit-idl | `gf-codegen emit-idl <sor> --out …` 生成 `gf_types.idl` | □ | □ | □ | |
| R6.5 | idlc 包装 | `bash scripts/run_idlc.sh …`：无 idlc 则 SKIP 不失败 | □ | □ | □ | |
| R6.6 | Dependencies | 有 cyclonedds 源码树时可 add_subdirectory；无则 stub | □ | □ | □ | |
| R6.7 | 边界 | 真 Cyclone/vsomeip+Boost **未**强制下载；完整 CommonAPI 不做 | □ | □ | □ | |

---

## R7 — T / A（GMT · ARXML）

| # | 检查项 | 怎么验 | 通过 | 需改 | 延后 | 备注 |
|---|--------|--------|:----:|:----:|:----:|------|
| R7.1 | 一键 smoke | `bash scripts/smoke_ta.sh` | □ | □ | □ | |
| R7.2 | architect lineage | `GMT architect lineage --project projects/oem_a/afc_with_uss/project.yaml` → PASS | □ | □ | □ | |
| R7.3 | architect dag | `GMT architect dag --project …` 输出 nodes/edges JSON | □ | □ | □ | |
| R7.4 | measure export | `GMT measure export --in tools/gmt/fixtures/session_stub.jsonl --out /tmp/x.mcap`；文件以 `\x89MCAP0` 开头 | □ | □ | □ | |
| R7.5 | ARXML import | `gf-codegen import arxml schemas/examples/oem/demo_faracon_subset.arxml` → candidates 含 EgoMotion | □ | □ | □ | |
| R7.6 | CI 挂钩 | `ci/scripts/smoke.sh` 含 GMT architect + pytest | □ | □ | □ | |
| R7.7 | 边界 | 无 Foxglove 桥；无内嵌 FARACON；ARXML 仅为子集 | □ | □ | □ | |

---

## 建议 Review 顺序与耗时

| 顺序 | 块 | 建议方式 | 约耗时 |
|------|----|----------|--------|
| 1 | R0 | 读文档 | 15–20 min |
| 2 | R1 | 手开 GUI | 30–45 min |
| 3 | R2 + R3 | CLI + 对照 wiring | 25–40 min |
| 4 | R4 | smoke 脚本 | 10–15 min |
| 5 | R5 + R6 | smoke 脚本 | 15–20 min |
| 6 | R7 | smoke_ta | 10–15 min |
| 7 | （可选）`bash ci/scripts/smoke.sh` | 全量 CI，需 bootstrap/iceoryx | 较长 |

---

## 快速冒烟合集（不经 GUI）

```bash
# 在仓库根
source .venv/bin/activate
pip install -e "tools/codegen[dev]" -e "tools/gmt[dev]"

bash scripts/smoke_eu_stub.sh
bash scripts/smoke_bd_stub.sh
bash projects/oem_b/adc_full/scripts/smoke_mcu_desktop.sh
bash scripts/smoke_ta.sh

pytest tools/codegen/tests tools/gmt/tests -q
```

---

## Review 发现登记（边审边填）

| ID | 子轨 | 严重度（阻塞/重要/建议） | 现象 | 期望修改 | 状态 |
|----|------|--------------------------|------|----------|------|
| | | | | | open |
| | | | | | |

审完后把「需改」项按阻塞优先交给我改即可。
