# mcu.cp_gateway

Reference **AP-side gateway** for `ap_mcu_cp` topology.

- Inward: `gf_ara::com` semantic services (e.g. trajectory in, actuator status out)
- Outward: customer IPC protocol to AUTOSAR CP on MCU (no Giraffe runtime on MCU)

Mapping from SOR `cp_ipc_mappings[]`. Desktop: pair with [cp_ipc_peer simulator](../../simulators/cp_ipc_peer/).

Parent: [adapters/README.md](../README.md)
