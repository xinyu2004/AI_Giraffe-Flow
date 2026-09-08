# Host/SIL Foxglove BEV. Debug only — not for production profile.
# Prefer codegen (${GF_GENERATED_DIR}/src/obs_foxglove_main.cpp) for iceoryx path.

find_package(ZLIB REQUIRED)
find_package(Threads REQUIRED)

# Paint + WS only (no iceoryx / GfChannel). Gold BEV lives here.
add_library(gf_foxglove_paint STATIC
  src/png.cpp
  src/ws_hub.cpp
  src/bev_compose.cpp
  src/bev_ndjson.cpp
)
target_include_directories(gf_foxglove_paint PUBLIC
  "${CMAKE_CURRENT_SOURCE_DIR}/include"
)
target_link_libraries(gf_foxglove_paint PUBLIC ZLIB::ZLIB)
set_target_properties(gf_foxglove_paint PROPERTIES POSITION_INDEPENDENT_CODE ON)

# Host octave standalone: NDJSON stdin → paint → Foxglove (no RouDi).
add_executable(gf_host_bev_ws src/host_bev_main.cpp)
target_link_libraries(gf_host_bev_ws PRIVATE gf_foxglove_paint Threads::Threads)
target_compile_definitions(gf_host_bev_ws PRIVATE _GNU_SOURCE)

if(GF_BUILD_TESTS)
  add_executable(gf_foxglove_ndjson_smoke test/test_bev_ndjson.cpp)
  target_link_libraries(gf_foxglove_ndjson_smoke PRIVATE gf_foxglove_paint)
  add_test(NAME gf_foxglove_ndjson_smoke COMMAND gf_foxglove_ndjson_smoke)
endif()

if(NOT GF_USE_GENERATED)
  message(STATUS "gf_foxglove_ws / gf_foxglove_core: skipped (GF_USE_GENERATED=OFF); gf_host_bev_ws built")
  return()
endif()

# Board/SIL extras: POD ingest + camera channel.
add_library(gf_foxglove_core STATIC
  src/bev_ingest.cpp
  src/camera.cpp
)
target_include_directories(gf_foxglove_core PUBLIC
  "${CMAKE_CURRENT_SOURCE_DIR}/include"
  "${GF_GENERATED_DIR}/include"
)
target_link_libraries(gf_foxglove_core PUBLIC gf_foxglove_paint)
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
