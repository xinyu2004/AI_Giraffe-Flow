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

# log before optional modules so exec/EM (and others) can link gf_ara::log
# regardless of runtime_modules[] order in req.yaml.
if(NOT TARGET gf_ara_log AND EXISTS "${CMAKE_SOURCE_DIR}/middleware/log/CMakeLists.txt")
  add_subdirectory("${CMAKE_SOURCE_DIR}/middleware/log")
  message(STATUS "Giraffe Flow: helper module log (early)")
endif()

# --- optional runtime modules from req.runtime_modules ---
if(DEFINED GF_RUNTIME_MODULES)
  foreach(_gf_mod IN LISTS GF_RUNTIME_MODULES)
    if(_gf_mod STREQUAL "core" OR _gf_mod STREQUAL "com" OR _gf_mod STREQUAL "osal"
       OR _gf_mod STREQUAL "trace" OR _gf_mod STREQUAL "runtime")
      # runtime is added after exec/phm/sm/collector/log (see below)
      continue()
    endif()
    # Already added early (e.g. log) or by a prior entry — do not add_subdirectory twice.
    if(TARGET gf_ara_${_gf_mod})
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
foreach(_gf_extra IN ITEMS sm collector ucm log per tsync diag)
  if(TARGET gf_ara_${_gf_extra})
    continue()
  endif()
  set(_gf_path "${CMAKE_SOURCE_DIR}/middleware/${_gf_extra}")
  if(EXISTS "${_gf_path}/CMakeLists.txt")
    add_subdirectory("${_gf_path}")
    message(STATUS "Giraffe Flow: helper module ${_gf_extra}")
  endif()
endforeach()

# --- process bring-up (SIL/HIL shared; after exec/phm/sm/collector/log) ---
if(NOT TARGET gf_ara_runtime)
  if(TARGET gf_ara_exec AND TARGET gf_ara_phm AND TARGET gf_ara_sm
     AND TARGET gf_ara_collector AND TARGET gf_ara_log
     AND EXISTS "${CMAKE_SOURCE_DIR}/middleware/runtime/CMakeLists.txt")
    add_subdirectory("${CMAKE_SOURCE_DIR}/middleware/runtime")
    message(STATUS "Giraffe Flow: helper module runtime")
  endif()
endif()

# DoIP OTA server + session / UCM-OTA smokes (diag may be added before ucm in runtime_modules).
if(TARGET gf_ara_diag AND TARGET gf_ara_ucm AND TARGET gf_ara_sm AND TARGET gf_ara_collector)
  if(NOT TARGET gf_doip_ota_server)
    add_executable(gf_doip_ota_server
      "${CMAKE_SOURCE_DIR}/middleware/diag/src/doip_ota_server_main.cpp")
    target_link_libraries(gf_doip_ota_server PRIVATE gf_ara::diag gf_ara::ucm gf_ara::sm
        gf_ara::collector gf_ara::log)
  endif()
  if(GF_BUILD_TESTS AND NOT TARGET gf_doip_session_smoke)
    add_executable(gf_doip_session_smoke
      "${CMAKE_SOURCE_DIR}/middleware/diag/testcases/smoke_doip_session.cpp")
    target_link_libraries(gf_doip_session_smoke PRIVATE gf_ara::diag gf_ara::ucm gf_ara::sm
                                                        gf_ara::collector)
    add_test(NAME gf_doip_session_smoke COMMAND gf_doip_session_smoke)
  endif()
endif()
if(GF_BUILD_TESTS AND TARGET gf_ara_ucm AND TARGET gf_ara_phm AND TARGET gf_ara_sm
   AND TARGET gf_ara_collector AND NOT TARGET gf_ucm_ota_smoke)
  add_executable(gf_ucm_ota_smoke
    "${CMAKE_SOURCE_DIR}/middleware/ucm/testcases/smoke_ota.cpp")
  target_link_libraries(gf_ucm_ota_smoke PRIVATE gf_ara::ucm gf_ara::phm gf_ara::sm
                                                 gf_ara::collector)
  add_test(NAME gf_ucm_ota_smoke COMMAND gf_ucm_ota_smoke)
endif()

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
# Prefer tools/<path> for debug_bridge/*; then projects/<oem>/<sku>/apps/<path>;
# fall back to shared apps/<path>. Binary dir stays build/apps/<path> for run scripts.
if(DEFINED GF_APPS)
  foreach(_gf_app IN LISTS GF_APPS)
    set(_gf_apath "")
    if(_gf_app MATCHES "^debug_bridge/"
       AND EXISTS "${CMAKE_SOURCE_DIR}/tools/${_gf_app}/CMakeLists.txt")
      set(_gf_apath "${CMAKE_SOURCE_DIR}/tools/${_gf_app}")
    endif()
    if(_gf_apath STREQUAL "" AND DEFINED GF_PROJECT_DIR AND NOT GF_PROJECT_DIR STREQUAL "")
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
    # iceoryx demo / main-chain apps
    if(NOT GF_WITH_ICEORYX)
      if(_gf_app STREQUAL "demo_pipeline"
         OR _gf_app STREQUAL "simulators/uss_feed"
         OR _gf_app STREQUAL "adapters/vehicle_can_gateway"
         OR _gf_app STREQUAL "perception/fcm"
         OR _gf_app STREQUAL "sensing/uss"
         OR _gf_app STREQUAL "planning/driving"
         OR _gf_app STREQUAL "debug_bridge/iox_obs_tap"
         OR _gf_app STREQUAL "debug_bridge/iox_obs_inject")
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
