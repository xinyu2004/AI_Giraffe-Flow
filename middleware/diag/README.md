# middleware/diag

ARA-inspired **Diagnostics** (`gf_ara::diag`).

| 层 | 标准 | 本仓行为 |
|----|------|----------|
| 应用 | **ISO 14229** UDS + NRC | `UdsDispatcher`（完整核心 SID）；0x27/0x29 → `.so/.dll` 插件 |
| 传输 | **ISO 13400** DoIP（依赖 14229） | `DoipTcpServer` / Client；不可单独启用 |
| CAN | （无 DoIP 时） | AP **不做 ISO-TP**；完整 UDS PDU 交 MCU（`0xFE` 前缀 handoff / 跨域契约） |

```bash
ctest --test-dir build -R 'gf_diag_doip_smoke|gf_uds_nrc_smoke|gf_doip_session_smoke' --output-on-failure
bash scripts/verify/oem_a_afc_with_uss/smoke_doip_ota.sh
```

配置：`platform/diag.yaml` → `standards.iso_14229_uds` / `standards.iso_13400_doip`（父/子）。

Parent: [middleware/README.md](../README.md) · FuSa: [diag_cases.md](../../fusa/cases/diag_cases.md).
