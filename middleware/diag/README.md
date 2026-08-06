# middleware/diag

ARA-inspired **Diagnostics** (`gf_ara::diag`).

| 层 | 标准 | 本仓行为 |
|----|------|----------|
| 应用 | **ISO 14229** UDS + NRC | `UdsDispatcher`（核心 SID）；0x27/0x29 → `.so/.dll` 插件 |
| 传输 | **ISO 13400** DoIP（依赖 14229） | `DoipTcpServer` / Client；不可单独启用 |
| OTA 下载 | `ota_transfer.mode` | 默认 **0x38→0x36→0x37**；可选 0x34 / SIL 0x31 |
| 时序 | `timing.*` | S3Server、TesterPresent 周期、P2/P2*、security_delay |
| CAN | （无 DoIP 时） | AP **不做 ISO-TP**；完整 UDS PDU 交 MCU |

配置：`platform/diag.yaml`（gf-config 页 2 · 诊断）。操作面：**GMT → OTA**（只读跟从 yaml）。说明：[DOIP_OTA.md](../../docs/zh/operations/DOIP_OTA.md)。

```bash
ctest --test-dir build -R 'gf_diag_doip_smoke|gf_uds_nrc_smoke|gf_doip_session_smoke' --output-on-failure
bash projects/oem_a/afc_with_uss/scripts/verify/smoke_doip_ota.sh
```

假包（SIL）：`bash scripts/make_sil_swu.sh /tmp/gf_demo.swu`

Parent: [middleware/README.md](../README.md) · FuSa: [diag_cases.md](../../fusa/cases/diag_cases.md).
