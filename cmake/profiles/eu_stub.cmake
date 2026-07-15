# P1 Track E/U: link exec/phm/ucm/diag stubs (no iceoryx apps).
set(GF_SKU_APPLIED TRUE)
set(GF_SKU_VARIANT "eu_stub")

set(GF_WITH_ICEORYX OFF CACHE BOOL "" FORCE)
set(GF_WITH_SOMEIP OFF CACHE BOOL "" FORCE)
set(GF_WITH_DDS OFF CACHE BOOL "" FORCE)
set(GF_WITH_CROSS_DOMAIN_IPC OFF CACHE BOOL "" FORCE)

set(GF_RUNTIME_MODULES core com exec phm ucm diag)
set(GF_APPS)
