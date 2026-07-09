# MCU（AUTOSAR CP）与 AP 双拓扑

| topology | MCU | AP |
|----------|-----|-----|
| `ap_only` | 无 | control 等组件或 sim |
| `ap_mcu_cp` | AUTOSAR CP，**零 gf 代码** | `mcu.cp_gateway` + IPC |

`gf_ara::com` 仅覆盖 AP；MCU 能力由 gateway 暴露为 semantic 服务。

SOR：`cp_ipc_mappings[]`、`compute_domains[]`。

桌面调试：`simulators/cp_ipc_peer`。
