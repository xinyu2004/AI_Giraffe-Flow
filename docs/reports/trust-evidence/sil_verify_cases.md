# SIL verify — 集成场景（L3）

场景级 case：脚本 + 环境 + **可观察**断言。薄 app / SKU stub 通过本层「集成进来」，不做逐 main 单元 smoke。

**分两类：**

| 类别 | 用途 | 是否进认证前期 pack |
|------|------|---------------------|
| **trust** | 主链 / exec·phm·健康恢复等板级行为 | 是（L3 默认） |
| **debug-path** | Observability / Inject 等调试通路 | **否**；只证明实时性、稳定性、不拖垮主链 |

### 模板

```markdown
### SIL-xx — 标题
- 类别: trust | debug-path
- 脚本: …
- 前置: …
- 环境: …
- 步骤: …
- 期望: …
- 状态: active|later
```

## Trust（认证前期相关）

### SIL-01 — 双进程 demo
- 类别: trust
- 脚本: `scripts/verify/oem_a_afc_with_uss/smoke_sil.sh`
- 前置: deps bootstrap
- 期望: compile + iox demo 绿
- 状态: active

### SIL-02 — 多进程主链
- 类别: trust
- 脚本: `scripts/verify/oem_a_afc_with_uss/smoke_sil_multiproc.sh`
- 步骤: compile_sil → run_sil_multiproc
- 期望: 有限帧 Trajectory / exec·phm 断言（脚本内）
- 状态: active

### SIL-03 — PHM miss → recover
- 类别: trust
- 脚本: `scripts/verify/oem_a_afc_with_uss/smoke_sil_phm_fault.sh`
- 环境: `GF_PHM_FAULT_MS=500`（默认）
- 期望: gateway.log 含 `AliveMissed|DeadlineMissed` 与 `phm recovered`；e2e 仍通
- 状态: active

### SIL-06 — MCU desktop peer
- 类别: trust
- 脚本: `scripts/verify/oem_b_adc_full/smoke_mcu_desktop.sh`
- 期望: cross_domain_ipc 桌面联调绿
- 状态: active

可选：`GF_TRUST_EVIDENCE_SIL=1 bash scripts/verify/trust_evidence_modules.sh`（默认只跑 SIL-03 类 trust 场景，见脚本）。

## Debug-path（不进认证支撑）

调试 / 联调通路：目标是 **实时性、稳定性、可选关闭（production profile）**，**不**作为 ASIL / Safety Case 证据。与 GMT 同属主机/调试侧；板端仅要求「开时不拖垮主链，关时主链自洽」。

### SIL-DBG-01 — Observability Tag→MCAP
- 类别: debug-path
- 脚本: `scripts/verify/oem_a_afc_with_uss/smoke_sil_observability.sh`
- 证明重点: Record/Tag→MCAP 通路可重复；对主链帧率/存活的干扰可接受（工程门槛，非认证声明）
- 期望: session.mcap 等产物（见脚本）
- 状态: active（工程回归）；**trust-pack: 否**

### SIL-DBG-02 — Inject 路径
- 类别: debug-path
- 脚本: `smoke_sil_inject.sh` / `smoke_sil_inject_b2.sh`
- 证明重点: inject 可复现、稳定；production 应可关（见 ROADMAP T4）
- 期望: inject 路径可跑通
- 状态: active（工程回归）；**trust-pack: 否**
