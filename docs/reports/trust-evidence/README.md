# Trust-evidence case index

政策说明：[TRUST_EVIDENCE.md](../../zh/operations/TRUST_EVIDENCE.md)

| 层 | 含义 |
|----|------|
| L1 | 板级库 `middleware/**/testcases` ↔ `CASE` 行 |
| L2 | gf-codegen 生成物保证（pytest / golden） |
| L3 | SIL 集成场景（`scripts/verify/.../smoke_*.sh`） |

**不含 GMT**（主机工具）。

## L1 — Middleware / bindings

| 模块 | Cases | 前缀 | Smoke | 状态 |
|------|-------|------|-------|------|
| core | [core_cases.md](core_cases.md) | CORE | `gf_core_smoke` | active |
| osal | [osal_cases.md](osal_cases.md) | OSAL | `gf_osal_smoke` · `gf_osal_process_smoke` | active |
| com | [com_cases.md](com_cases.md) | COM | `gf_com_loopback_smoke` | active |
| exec | [exec_cases.md](exec_cases.md) | EXEC / EM / EMD | `gf_exec_smoke` · `gf_exec_em_smoke` · `gf_em_daemon_smoke` | active |
| sm | [sm_cases.md](sm_cases.md) | SM | `gf_sm_fg_smoke` | active |
| phm | [phm_cases.md](phm_cases.md) | PHM | `gf_phm_alive_deadline_smoke` | active |
| collector | [collector_cases.md](collector_cases.md) | COLL | `gf_collector_smoke` | active |
| diag | [diag_cases.md](diag_cases.md) | DIAG | `gf_diag_doip_smoke` | skeleton |
| ucm | [ucm_cases.md](ucm_cases.md) | UCM | `gf_ucm_package_manager_smoke` | skeleton |
| iceoryx | [iceoryx_cases.md](iceoryx_cases.md) | IOX | `gf_iox_binding_smoke` | active（需 iox） |
| someip | [someip_cases.md](someip_cases.md) | SIP | `gf_someip_binding_smoke` | active |
| dds | [dds_cases.md](dds_cases.md) | DDS | `gf_dds_binding_smoke` | active |
| cross_domain_ipc | [cross_domain_ipc_cases.md](cross_domain_ipc_cases.md) | XIPC | `gf_cross_domain_ipc_smoke` | active |
| log | [log_cases.md](log_cases.md) | LOG | — | later |
| hal | [hal_cases.md](hal_cases.md) | HAL | — | later |
| trace | [trace_cases.md](trace_cases.md) | TRACE | — | later |

`third_party/` 不建 Giraffe cases。

## L2 — Codegen

| 文档 | 说明 |
|------|------|
| [gf_codegen_cases.md](gf_codegen_cases.md) | 生成规则 / golden / 生成物进 SIL |

## L3 — SIL verify

| 文档 | 说明 |
|------|------|
| [sil_verify_cases.md](sil_verify_cases.md) | **trust** 场景进 pack；Tag→MCAP / Inject 标为 **debug-path**（不进认证支撑） |

## 复现

```bash
cmake -B build -DGF_BUILD_TESTS=ON   # + SKU / iceoryx 按需
cmake --build build -j"$(nproc)"
bash scripts/verify/trust_evidence_modules.sh
```
