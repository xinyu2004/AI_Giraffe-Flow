# P1 Track M: MCU desktop联调 — no iceoryx / no real MCU.
# Builds cross_domain_ipc + mcu_cp_gateway + cp_ipc_peer only.
set(GF_SKU_APPLIED TRUE)
set(GF_SKU_VARIANT "mcu_desktop")

set(GF_WITH_ICEORYX OFF CACHE BOOL "" FORCE)
set(GF_WITH_SOMEIP OFF CACHE BOOL "" FORCE)
set(GF_WITH_DDS OFF CACHE BOOL "" FORCE)
set(GF_WITH_CROSS_DOMAIN_IPC ON CACHE BOOL "" FORCE)

set(GF_RUNTIME_MODULES core com)
set(GF_APPS adapters/mcu_cp_gateway simulators/cp_ipc_peer)
