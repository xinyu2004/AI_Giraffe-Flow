# Consume SKU fragment (GF_RUNTIME_MODULES / GF_APPS / GF_WITH_*) and add middleware + apps.
#
# Always-on: core, com, osal
# Optional modules: only if middleware/<name>/CMakeLists.txt exists
# Bindings: gated by GF_WITH_* (set by compose gf_build.cmake or cmake/profiles/*)

# --- foundation (always) ---
foreach(_gf_mod IN ITEMS core com osal)
  set(_gf_path "${CMAKE_SOURCE_DIR}/middleware/${_gf_mod}")
  if(EXISTS "${_gf_path}/CMakeLists.txt")
    add_subdirectory("${_gf_path}")
  else()
    message(FATAL_ERROR "Giraffe Flow: required module missing CMakeLists: ${_gf_path}")
  endif()
endforeach()

# --- optional runtime modules from req.runtime_modules ---
if(DEFINED GF_RUNTIME_MODULES)
  foreach(_gf_mod IN LISTS GF_RUNTIME_MODULES)
    if(_gf_mod STREQUAL "core" OR _gf_mod STREQUAL "com" OR _gf_mod STREQUAL "osal"
       OR _gf_mod STREQUAL "trace")
      continue()
    endif()
    set(_gf_path "${CMAKE_SOURCE_DIR}/middleware/${_gf_mod}")
    if(EXISTS "${_gf_path}/CMakeLists.txt")
      add_subdirectory("${_gf_path}")
      message(STATUS "Giraffe Flow: runtime module ${_gf_mod}")
    else()
      message(STATUS "Giraffe Flow: skip runtime module '${_gf_mod}' (no CMakeLists yet)")
    endif()
  endforeach()
endif()

# --- SIL helpers (sm / collector / ucm): build if present and not already added ---
foreach(_gf_extra IN ITEMS sm collector ucm)
  if(TARGET gf_ara_${_gf_extra})
    continue()
  endif()
  set(_gf_path "${CMAKE_SOURCE_DIR}/middleware/${_gf_extra}")
  if(EXISTS "${_gf_path}/CMakeLists.txt")
    add_subdirectory("${_gf_path}")
    message(STATUS "Giraffe Flow: helper module ${_gf_extra}")
  endif()
endforeach()

# --- bindings from req.bindings → GF_WITH_* ---
macro(gf_add_binding _flag _subdir)
  if(${_flag})
    set(_gf_bpath "${CMAKE_SOURCE_DIR}/middleware/bindings/${_subdir}")
    if(EXISTS "${_gf_bpath}/CMakeLists.txt")
      add_subdirectory("${_gf_bpath}")
      message(STATUS "Giraffe Flow: binding ${_subdir} (${_flag}=ON)")
    else()
      message(STATUS "Giraffe Flow: skip binding '${_subdir}' (${_flag}=ON but no CMakeLists)")
    endif()
  endif()
endmacro()

gf_add_binding(GF_WITH_ICEORYX iceoryx)
gf_add_binding(GF_WITH_SOMEIP someip)
gf_add_binding(GF_WITH_DDS dds)
gf_add_binding(GF_WITH_CROSS_DOMAIN_IPC cross_domain_ipc)

# --- apps from req.apps ---
# Prefer projects/<oem>/<sku>/apps/<path> when GF_PROJECT_DIR is set (SKU stubs);
# fall back to shared apps/<path>. Binary dir stays build/apps/<path> for run scripts.
if(DEFINED GF_APPS)
  foreach(_gf_app IN LISTS GF_APPS)
    set(_gf_apath "")
    if(DEFINED GF_PROJECT_DIR AND NOT GF_PROJECT_DIR STREQUAL "")
      if(EXISTS "${GF_PROJECT_DIR}/apps/${_gf_app}/CMakeLists.txt")
        set(_gf_apath "${GF_PROJECT_DIR}/apps/${_gf_app}")
      endif()
    endif()
    if(_gf_apath STREQUAL "" AND EXISTS "${CMAKE_SOURCE_DIR}/apps/${_gf_app}/CMakeLists.txt")
      set(_gf_apath "${CMAKE_SOURCE_DIR}/apps/${_gf_app}")
    endif()
    if(_gf_apath STREQUAL "")
      message(STATUS "Giraffe Flow: skip app '${_gf_app}' (missing CMakeLists)")
      continue()
    endif()
    # iceoryx demo / multiproc main-chain apps
    if(NOT GF_WITH_ICEORYX)
      if(_gf_app STREQUAL "demo_pipeline"
         OR _gf_app STREQUAL "simulators/uss_feed"
         OR _gf_app STREQUAL "adapters/vehicle_can_gateway"
         OR _gf_app STREQUAL "perception/fcm"
         OR _gf_app STREQUAL "sensing/uss"
         OR _gf_app STREQUAL "planning/driving"
         OR _gf_app STREQUAL "tools/iox_obs_tap"
         OR _gf_app STREQUAL "tools/iox_obs_inject")
        message(STATUS "Giraffe Flow: skip app '${_gf_app}' (needs GF_WITH_ICEORYX)")
        continue()
      endif()
    endif()
    # MCU desktop apps need cross_domain_ipc
    if(NOT GF_WITH_CROSS_DOMAIN_IPC)
      if(_gf_app STREQUAL "adapters/mcu_cp_gateway"
         OR _gf_app STREQUAL "simulators/cp_ipc_peer")
        message(STATUS "Giraffe Flow: skip app '${_gf_app}' (needs GF_WITH_CROSS_DOMAIN_IPC)")
        continue()
      endif()
    endif()
    add_subdirectory("${_gf_apath}" "${CMAKE_BINARY_DIR}/apps/${_gf_app}")
    message(STATUS "Giraffe Flow: app ${_gf_app} ← ${_gf_apath}")
  endforeach()
endif()
