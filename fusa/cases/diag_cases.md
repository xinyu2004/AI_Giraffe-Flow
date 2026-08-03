# diag — trust cases

| Case ID | 期望 | 复现 |
|---------|------|------|
| DIAG-01…05 | 进程内 DoipStack | `ctest -R gf_diag_doip_smoke` |
| UDS-00 | 13400 依赖 14229 | `ctest -R gf_uds_nrc_smoke` |
| UDS-10/10N/3E/22/27/29/2E/NS/MCU | 正响应 + NRC + MCU PDU handoff | 同上 |
| DOIP-S01…05 | TCP DoIP → UDS → OTA / Collector | `ctest -R gf_doip_session_smoke` |
| DOIP-LIVE | `gf_doip_ota_server` | `smoke_doip_ota.sh` |
