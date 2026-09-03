# Fallback SKU when -DGF_SKU_CMAKE is unset (host CI / middleware desktop).
# Apps come from a project compose; this profile is runtime + iceoryx only.
set(GF_SKU_APPLIED TRUE)
set(GF_SKU_VARIANT "desktop_default")

set(GF_WITH_ICEORYX ON CACHE BOOL "" FORCE)
set(GF_WITH_SOMEIP OFF CACHE BOOL "" FORCE)
set(GF_WITH_DDS OFF CACHE BOOL "" FORCE)
set(GF_WITH_CROSS_DOMAIN_IPC OFF CACHE BOOL "" FORCE)

set(GF_RUNTIME_MODULES core com log)
set(GF_APPS)
