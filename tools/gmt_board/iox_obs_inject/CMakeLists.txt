# Observability inject (P2.5 G3) — session JSONL → iceoryx publish
add_executable(gf_iox_obs_inject src/main.cpp)
target_link_libraries(gf_iox_obs_inject PRIVATE gf_ara::com_iceoryx)
add_dependencies(gf_iox_obs_inject iox-roudi)

if(NOT GF_USE_GENERATED)
  message(FATAL_ERROR "gf_iox_obs_inject requires GF_USE_GENERATED=ON")
endif()
target_include_directories(gf_iox_obs_inject PRIVATE "${GF_GENERATED_DIR}/include")
target_compile_definitions(gf_iox_obs_inject PRIVATE GF_USE_GENERATED=1)
