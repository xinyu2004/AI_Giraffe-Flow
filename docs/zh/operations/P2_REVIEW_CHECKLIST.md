# P2 完整 Review 清单

> 对应计划：[P2_PLAN.md](P2_PLAN.md) · 路线图：[ROADMAP.md](ROADMAP.md) · 配置规格：[MIDDLEWARE_CONFIG_PLAN.md](MIDDLEWARE_CONFIG_PLAN.md)  
> 用法：按 **R0 → G** 顺序逐项过；每项勾选「通过 / 需改 / 延后」，备注写修改意图。  
> 前置：仓库根 · `source .venv/bin/activate` · `pip install -e tools/codegen[dev] -e tools/gmt[dev] -e tools/config[dev]`（按需）

**整体判定（review 结束后填）：**

| 结论 | □ 通过可进 P3 | □ 有阻塞修改后再验收 | □ 部分延后 P3 |
|------|---------------|----------------------|---------------|
| Reviewer | | 日期 | |

---

## R0 — 边界与主链

| # | 检查项 | 期望 | 通过 | 需改 | 延后 | 备注 |
|---|--------|------|:----:|:----:|:----:|------|
| R0.1 | P2 范围 | 真正可运行 SIL + 最小可观测 + platform 五 yaml；**无 DEM** | □ | □ | □ | |
| R0.2 | 工具边界 | **gf-config** 写 req/wiring/platform；**codegen** compose/lint/generate；**GMT** 只读 | □ | □ | □ | |
| R0.3 | 主演示链 | `afc_with_uss`：gateway → fcm/uss → planning；**无 FAPA** | □ | □ | □ | |
| R0.4 | 明确不做 | 真 MCU/DoIP 台架/量产 OTA；GMT 可写配置；三栈量产级；ISO 26262 | □ | □ | □ | |

---

## Cfg — gf-config A/B/C

| # | 检查项 | 怎么验 | 通过 | 需改 | 延后 | 备注 |
|---|--------|--------|:----:|:----:|:----:|------|
| Cfg.1 | A · SKU 瘦身 | `gf-config …/project.yaml`：topology / capabilities / runtime_modules；apps 在高级折叠 | □ | □ | □ | |
| Cfg.2 | B · 信号链接 | 画布拖线；右侧连线/Lineage；布局保持 | □ | □ | □ | |
| Cfg.3 | C · 平台 | 子页编辑 exec/phm/diag/log/ucm；进程候选来自 wiring（无 external） | □ | □ | □ | |
| Cfg.4 | Save / Verify | Ctrl+S 落盘 A+B+C；Verify 前 flush；错 process 红 | □ | □ | □ | |

**代码：** `tools/config/src/gf_config/gui/{main_window,req_editor,platform_editor}.py`

---

## P — compose 吃 platform

| # | 检查项 | 怎么验 | 通过 | 需改 | 延后 | 备注 |
|---|--------|--------|:----:|:----:|:----:|------|
| P.1 | 读 platform | `project.yaml` → `platform:` 五路径 | □ | □ | □ | |
| P.2 | 坏 process 失败 | `pytest tools/codegen/tests/test_merge_platform.py -q` | □ | □ | □ | |
| P.3 | SOR 含 manifest | compose 后 `platform_manifest` 含 exec/phm/diag/log；**无 dem** | □ | □ | □ | |
| P.4 | bench golden | `pytest tools/codegen/tests/test_afc_bench_golden.py -q` | □ | □ | □ | |

```bash
python -m gf_codegen.compose --project projects/oem_a/afc_with_uss/project.yaml
pytest tools/codegen/tests/test_merge_platform.py tools/codegen/tests/test_afc_bench_golden.py -q
```

---

## R — 多进程 SIL

| # | 检查项 | 怎么验 | 通过 | 需改 | 延后 | 备注 |
|---|--------|--------|:----:|:----:|:----:|------|
| R.1 | 多进程 smoke | `bash projects/oem_a/afc_with_uss/scripts/smoke_sil_multiproc.sh` | □ | □ | □ | |
| R.2 | 端到端计数 | 日志可见 Trajectory / 各进程存活 | □ | □ | □ | |
| R.3 | 双进程回归 | `bash …/smoke_sil.sh` 仍绿 | □ | □ | □ | |

---

## X — exec / phm 挂主链

| # | 检查项 | 怎么验 | 通过 | 需改 | 延后 | 备注 |
|---|--------|--------|:----:|:----:|:----:|------|
| X.1 | Offer→Running | multiproc 设 `GF_PLATFORM_DIR=…/platform`；日志有 Running | □ | □ | □ | |
| X.2 | Alive | 读 `phm.yaml`；周期 ReportAlive | □ | □ | □ | |
| X.3 | 故障注入 | `GF_PHM_FAULT_MS=…` → AliveMiss 可观测后恢复 | □ | □ | □ | |
| X.4 | OTA Pause 文档 | [PHM_OTA_PAUSE.md](PHM_OTA_PAUSE.md) / [OTA_SPIKE.md](OTA_SPIKE.md) 可读 | □ | □ | □ | |

---

## O / F — 可观测 + Foxglove

| # | 检查项 | 怎么验 | 通过 | 需改 | 延后 | 备注 |
|---|--------|--------|:----:|:----:|:----:|------|
| O.1 | Record→Tag→MCAP | `bash …/smoke_sil_observability.sh` → `build/observability/session.mcap` ≥1 topic | □ | □ | □ | |
| O.2 | 演示步骤 | 按 [OBSERVABILITY_DEMO.md](OBSERVABILITY_DEMO.md) 约 10 min | □ | □ | □ | |
| F.1 | Foxglove | `GMT bridge foxglove --mcap build/observability/session.mcap`；Studio 打开 | □ | □ | □ | |
| F.2 | 字段说明 | SIL stub 多数字段为 0 **属预期** | □ | □ | □ | |

---

## B — CycloneDDS 旁路

| # | 检查项 | 怎么验 | 通过 | 需改 | 延后 | 备注 |
|---|--------|--------|:----:|:----:|:----:|------|
| B.1 | 依赖钉扎 | `deps/versions.lock.md` → cyclonedds **0.10.5**；`bootstrap_deps.sh` 可拉 | □ | □ | □ | |
| B.2 | 真收发 | `bash scripts/smoke_bd_cyclone.sh` → backend=cyclonedds，≥1 event | □ | □ | □ | |
| B.3 | 边界文档 | [CYCLONEDDS_BYPASS.md](CYCLONEDDS_BYPASS.md)：主链 iceoryx；vsomeip stub | □ | □ | □ | |
| B.4 | stub 回归 | `bash scripts/smoke_bd_stub.sh` | □ | □ | □ | |

---

## G — 收口

| # | 检查项 | 怎么验 | 通过 | 需改 | 延后 | 备注 |
|---|--------|--------|:----:|:----:|:----:|------|
| G.1 | 版本锁 | iceoryx v2.0.8；cyclonedds 0.10.5；与 DEPENDENCIES 一致 | □ | □ | □ | |
| G.2 | bench golden | `test_afc_bench_golden.py` 绿；（可选）本地 `golden/gf.sor.json` 深比对 | □ | □ | □ | |
| G.3 | 证据包 | `bash scripts/collect_p2_evidence.sh`；`evidence_pack/p2_afc_with_uss/` 有样例 | □ | □ | □ | |
| G.4 | Review 本清单 | 本文件填完整体判定 | □ | □ | □ | |
| G.5 | （可选）OTA Spike | [OTA_SPIKE.md](OTA_SPIKE.md) | □ | □ | □ | |

---

## 建议顺序与耗时

| 顺序 | 块 | 方式 | 约耗时 |
|------|----|------|--------|
| 1 | R0 + 不做清单 | 读文档 | 10–15 min |
| 2 | Cfg | 手开 GUI | 25–40 min |
| 3 | P + G.2 | pytest | 5–10 min |
| 4 | R + X | multiproc smoke | 15–25 min |
| 5 | O/F | observability + Studio | 15–20 min |
| 6 | B | cyclone + stub | 15–30 min（含 bootstrap） |
| 7 | G.3 | collect evidence | 5–15 min |

---

## 快速冒烟合集（不经 GUI）

```bash
source .venv/bin/activate
pip install -e "tools/codegen[dev]" -e "tools/gmt[dev]"

pytest tools/codegen/tests/test_merge_platform.py \
       tools/codegen/tests/test_afc_bench_golden.py -q

bash projects/oem_a/afc_with_uss/scripts/smoke_sil_multiproc.sh
GF_SKIP_COMPILE=1 bash projects/oem_a/afc_with_uss/scripts/smoke_sil_observability.sh
bash scripts/smoke_bd_cyclone.sh

GF_EVIDENCE_UPDATE_GOLDEN=1 bash scripts/collect_p2_evidence.sh
```

---

## Review 发现登记

| ID | 子轨 | 严重度（阻塞/重要/建议） | 现象 | 期望修改 | 状态 |
|----|------|--------------------------|------|----------|------|
| | | | | | open |

审完后把「需改」项按阻塞优先交给实现即可。
