# mcu.cp_gateway

Reference **AP-side gateway** for `ap_mcu_cp` topology.

- Inward (full SKU): `gf_ara::com` semantic services (trajectory in, ego/actuator out)
- Outward: customer IPC protocol to AUTOSAR CP on MCU (**zero Giraffe code on MCU**)
- Desktop P1: Unix-socket lockstep with [`cp_ipc_peer`](../../simulators/cp_ipc_peer/) via `cross_domain_ipc`

```bash
bash projects/oem_b/adc_full/scripts/smoke_mcu_desktop.sh
```

Env: `GF_CP_IPC_PATH` (default `/tmp/gf_cp_ipc.sock`), `GF_MCU_PEER_ROUNDS` / `GF_MCU_GATEWAY_ROUNDS`.

Parent: [adapters/README.md](../README.md)
