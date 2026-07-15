# Trimmed SKU: core/com/log + iceoryx + demo_pipeline only (no uss_feed).
# Matches afc_no_uss-style req; used by CI configure smoke.
set(GF_SKU_APPLIED TRUE)
set(GF_SKU_VARIANT "desktop_minimal")

set(GF_WITH_ICEORYX ON CACHE BOOL "" FORCE)
set(GF_WITH_SOMEIP OFF CACHE BOOL "" FORCE)
set(GF_WITH_DDS OFF CACHE BOOL "" FORCE)
set(GF_WITH_CROSS_DOMAIN_IPC OFF CACHE BOOL "" FORCE)

set(GF_RUNTIME_MODULES core com log)
set(GF_APPS demo_pipeline)
