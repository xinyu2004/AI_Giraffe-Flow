# cross_domain IPC binding

AP ↔ peer domain (e.g. MCU AUTOSAR CP) when `topology: ap_mcu_cp`.

P1 desktop transport: **Unix stream socket** + framed POD payloads (`SocketTransport`).
Used by `mcu.cp_gateway` + `cp_ipc_peer`. Real SHM/customer IPC can replace the transport later.

Target: `gf_ara::cross_domain_ipc` · smoke test `gf_cross_domain_ipc_smoke`.

Parent: [bindings/README.md](../README.md)
