# SIL verify — 集成场景（L3）

场景级 case：脚本 + 环境 + **可观察**断言。薄 app / SKU stub 通过本层「集成进来」，不做逐 main 单元 smoke。

**分两类：**

| 类别 | 用途 | 是否进 Safety Case 证据集 |
|------|------|---------------------------|
| **fusa** | 主链 / exec·phm·健康恢复等板级行为 | 是（L3 默认） |
| **debug-path** | Observability / Inject 等调试通路 | **否**；只证明实时性、稳定性、不拖垮主链 |

### 模板

```markdown
### SIL-xx — 标题
- 类别: fusa | debug-path
- 脚本: …
- 前置: …
- 环境: …
- 步骤: …
- 期望: …
- 状态: active|later
```

## 最近复现（本机）

| 项 | 值 |
|----|-----|
| 时间 (UTC) | 2026-07-31T03:27:08Z |
| 命令（现） | `GF_FUSA_SIL=1 bash fusa/scripts/run_cases.sh` |
| L1 | 63 × `CASE … PASS`（0 FAIL） |
| L3 fusa | SIL-01 / 02 / 03 / EM-02 / 06 全部 OK |
| 日志 | `fusa/runs/cases_*.log`（默认不进仓） |

## FuSa（Safety Case 相关）

### SIL-01 — 双进程 demo
- 类别: fusa
- 脚本: `scripts/verify/oem_a_afc_with_uss/smoke_sil.sh`
- 前置: deps bootstrap
- 期望: compile + iox demo 绿
- 状态: active
- 最近: **PASS**（2026-07-31）

### SIL-02 — 主链 verify（有限帧）
- 类别: fusa
- 脚本: `scripts/verify/oem_a_afc_with_uss/smoke_sil_verify.sh`
- 步骤: compile_sil → run_sil_verify
- 期望: 有限帧 Trajectory / exec·phm 断言（脚本内）
- 状态: active
- 最近: **PASS**（2026-07-31）

### SIL-03 — PHM miss → recover
- 类别: fusa
- 脚本: `scripts/verify/oem_a_afc_with_uss/smoke_sil_phm_fault.sh`
- 环境: `GF_PHM_FAULT_MS=500`（默认）；注入在 **planning**（gateway 保持 0 以保 e2e）
- 期望: `planning.log` 含 `FAULT inject|AliveMissed|DeadlineMissed` 与 `recovered|fault window ended`；`gateway.log` 仍有 Trajectory
- 状态: active
- 最近: **PASS**（2026-07-31）

### SIL-SM-01 — PHM miss → SM health_fault（notify_sm）+ 共享 Collector
- 类别: fusa
- 脚本: `scripts/verify/oem_a_afc_with_uss/smoke_sil_sm_fg.sh`
- 环境: `GF_PHM_FAULT_TARGET=uss` · `GF_SM_ENTER_UPDATING_ON_FAULT=1` · `GF_COLLECTOR_STORE=…/runtime/collector/events.ndjson`
- 期望: `uss.log` 含 PHM miss · `sm: health_fault` · `collector: event` ·（可选）Updating/paused；`gateway.log` 仍有 Trajectory；共享 store 含 miss 事件
- 状态: active
- SG: SG-03 · SG-04（跨进程 store）

### SIL-T4 — production-release 关闭 debug-path
- 类别: fusa（SG-05 / ROADMAP T4）
- 脚本: `scripts/verify/oem_a_afc_with_uss/smoke_production_profile.sh`
- 环境: 临时 `profile: production-release` → compose；`GF_BUILD_DIR=build-prod`；`GF_FUSA_T4_SKIP_COMPILE=1` 可只跑 compose 断言
- 期望: `observability.json` live_tap off / record off；无 tap/inject 二进制；SIL-02 主链 verify PASS；退出时恢复 `vehicle-debug`
- 状态: active
- 门控: `GF_FUSA_T4=1 bash fusa/scripts/run_cases.sh`

### SIL-06 — MCU desktop peer
- 类别: fusa
- 脚本: `scripts/verify/oem_b_adc_full/smoke_mcu_desktop.sh`
- 期望: cross_domain_ipc 桌面联调绿
- 状态: active
- 最近: **PASS**（2026-07-31）

### SIL-EM-01 — PHM fault → EM 账本（软重启）
- 类别: fusa
- 库级复现: `ctest -R gf_exec_em_smoke`（EM-01…04）
- 说明: 无 `GF_EM_MANAGED` 时 `on_failure: restart` → soft relaunch；`GF_EM_SOFT_RESTART=1` 强制软路径
- 状态: active
- 最近: **PASS**（随 L1 `gf_exec_em_smoke`，2026-07-31）

### SIL-EM-02 — OS EM daemon（OSAL Spawn）+ relaunch
- 类别: fusa
- 库级: `ctest -R gf_em_daemon_smoke`（EMD-01…04）；进程原语 `ctest -R gf_osal_process_smoke`
- SIL: `scripts/verify/oem_a_afc_with_uss/smoke_sil_em_daemon.sh`
- 配置: `platform/em_launch.yaml` + `phm.yaml`（planning → `restart`）
- 期望: daemon 日志 `relaunch name=planning.driving`；子进程 `em os_restart_exit`；gateway 仍收到 Trajectory
- 机制: 子进程 exit **75** → `waitpid` → `fork/exec`；relaunch 时清 `GF_PHM_FAULT_MS`
- 状态: active
- 最近: **PASS**（2026-07-31）

一键（L1 + 上表 L3 fusa）：

```bash
GF_FUSA_SIL=1 bash fusa/scripts/run_cases.sh
# 跳过 MCU 桌面: GF_FUSA_SIL_MCU=0 …
# T4 production profile（另编 build-prod）: GF_FUSA_T4=1 …
```

## Debug-path（不进 Safety Case 默认证据集）

调试 / 联调通路：目标是 **实时性、稳定性、可选关闭（production profile）**，**不**作为 ASIL / Safety Case 默认证据。与 GMT 同属主机/调试侧；板端仅要求「开时不拖垮主链，关时主链自洽」。

### SIL-DBG-01 — Observability Tag→MCAP
- 类别: debug-path
- 脚本: `scripts/verify/oem_a_afc_with_uss/smoke_sil_observability.sh`
- 证明重点: Record/Tag→MCAP 通路可重复；对主链帧率/存活的干扰可接受（工程门槛，非认证声明）
- 期望: session.mcap 等产物（见脚本）
- 状态: active（工程回归）；**fusa-pack: 否**

### SIL-DBG-02 — Inject 路径
- 类别: debug-path
- 脚本: `smoke_sil_inject.sh` / `smoke_sil_inject_b2.sh`
- 证明重点: inject 可复现、稳定；production 应可关（见 ROADMAP T4）
- 期望: inject 路径可跑通
- 状态: active（工程回归）；**fusa-pack: 否**
