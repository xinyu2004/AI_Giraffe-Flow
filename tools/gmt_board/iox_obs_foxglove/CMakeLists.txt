# Host-side iceoryx → Foxglove WebSocket. Debug only — not for production profile.
# Prefer codegen (${GF_GENERATED_DIR}/src/obs_foxglove_main.cpp).

if(NOT GF_USE_GENERATED)
  message(FATAL_ERROR "gf_foxglove_ws requires GF_USE_GENERATED=ON")
endif()

find_package(ZLIB REQUIRED)

add_library(gf_foxglove_core STATIC
  src/png.cpp
  src/ws_hub.cpp
  src/bev_compose.cpp
  src/bev_ingest.cpp
  src/camera.cpp
)
target_include_directories(gf_foxglove_core PUBLIC
  "${CMAKE_CURRENT_SOURCE_DIR}/include"
  "${GF_GENERATED_DIR}/include"
)
target_link_libraries(gf_foxglove_core PUBLIC ZLIB::ZLIB)
if(TARGET gf_channel::channel)
  target_link_libraries(gf_foxglove_core PUBLIC gf_channel::channel)
endif()
set_target_properties(gf_foxglove_core PROPERTIES POSITION_INDEPENDENT_CODE ON)

set(_GF_FOX_GEN "${GF_GENERATED_DIR}/src/obs_foxglove_main.cpp")
if(EXISTS "${_GF_FOX_GEN}")
  add_executable(gf_foxglove_ws "${_GF_FOX_GEN}")
  message(STATUS "gf_foxglove_ws: using codegen ${_GF_FOX_GEN}")
else()
  message(WARNING "gf_foxglove_ws: codegen missing — fallback src/main_fallback.cpp")
  add_executable(gf_foxglove_ws src/main_fallback.cpp)
endif()

target_link_libraries(gf_foxglove_ws PRIVATE gf_foxglove_core gf_ara::com_iceoryx)
add_dependencies(gf_foxglove_ws iox-roudi)
target_include_directories(gf_foxglove_ws PRIVATE
  "${CMAKE_CURRENT_SOURCE_DIR}/include"
  "${GF_GENERATED_DIR}/include"
)
target_compile_definitions(gf_foxglove_ws PRIVATE GF_USE_GENERATED=1 _GNU_SOURCE)

if(GF_BUILD_TESTS)
  add_executable(gf_foxglove_bev_smoke test/test_foxglove_bev.cpp)
  target_link_libraries(gf_foxglove_bev_smoke PRIVATE gf_foxglove_core)
  add_test(NAME gf_foxglove_bev_smoke COMMAND gf_foxglove_bev_smoke)
endif()
