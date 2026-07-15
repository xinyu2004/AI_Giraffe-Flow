# cp_ipc_peer simulator

Simulates AUTOSAR CP IPC peer for `mcu.cp_gateway` — **no real MCU** on desktop.

Sends `IPC_CanInfo_*`, receives `IPC_TrajPlot_St` / `IPC_P_Parking_St` over `cross_domain_ipc`.

```bash
bash projects/oem_b/adc_full/scripts/smoke_mcu_desktop.sh
```

Parent: [simulators/README.md](../README.md)
