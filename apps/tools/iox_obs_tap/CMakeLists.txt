# Host-side iceoryx tap for live Foxglove (P2.5). Debug only — not for production profile.

add_executable(gf_iox_obs_tap src/main.cpp)
target_link_libraries(gf_iox_obs_tap PRIVATE gf_ara::com_iceoryx)
add_dependencies(gf_iox_obs_tap iox-roudi)

if(NOT GF_USE_GENERATED)
  message(FATAL_ERROR "gf_iox_obs_tap requires GF_USE_GENERATED=ON")
endif()
target_include_directories(gf_iox_obs_tap PRIVATE "${GF_GENERATED_DIR}/include")
target_compile_definitions(gf_iox_obs_tap PRIVATE GF_USE_GENERATED=1)
