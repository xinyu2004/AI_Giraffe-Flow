# Host-side iceoryx tap for live Foxglove. Debug only — not for production profile.
# Prefer codegen output (gf-codegen generate → ${GF_GENERATED_DIR}/src/obs_tap_main.cpp).

if(NOT GF_USE_GENERATED)
  message(FATAL_ERROR "gf_iox_obs_tap requires GF_USE_GENERATED=ON")
endif()

set(_GF_OBS_TAP_GEN "${GF_GENERATED_DIR}/src/obs_tap_main.cpp")
if(EXISTS "${_GF_OBS_TAP_GEN}")
  add_executable(gf_iox_obs_tap "${_GF_OBS_TAP_GEN}")
  message(STATUS "gf_iox_obs_tap: using codegen ${_GF_OBS_TAP_GEN}")
else()
  message(WARNING "gf_iox_obs_tap: codegen missing — fallback src/main.cpp (EgoMotion/Trajectory only)")
  add_executable(gf_iox_obs_tap src/main.cpp)
endif()

target_link_libraries(gf_iox_obs_tap PRIVATE gf_ara::com_iceoryx)
add_dependencies(gf_iox_obs_tap iox-roudi)
target_include_directories(gf_iox_obs_tap PRIVATE "${GF_GENERATED_DIR}/include")
target_compile_definitions(gf_iox_obs_tap PRIVATE GF_USE_GENERATED=1)
