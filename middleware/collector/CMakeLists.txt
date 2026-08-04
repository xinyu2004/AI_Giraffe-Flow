add_library(gf_ara_collector STATIC
  src/event_collector.cpp
)
add_library(gf_ara::collector ALIAS gf_ara_collector)

target_include_directories(gf_ara_collector PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_link_libraries(gf_ara_collector PUBLIC gf::osal gf_ara::core gf_ara::per)

if(GF_BUILD_TESTS)
  add_executable(gf_collector_smoke testcases/smoke_collector.cpp)
  target_link_libraries(gf_collector_smoke PRIVATE gf_ara::collector)
  add_test(NAME gf_collector_smoke COMMAND gf_collector_smoke)

  add_executable(gf_collector_xproc_smoke testcases/smoke_collector_xproc.cpp)
  target_link_libraries(gf_collector_xproc_smoke PRIVATE gf_ara::collector)
  add_test(NAME gf_collector_xproc_smoke COMMAND gf_collector_xproc_smoke)

  add_executable(gf_dem_lite_smoke testcases/smoke_dem_lite.cpp)
  target_link_libraries(gf_dem_lite_smoke PRIVATE gf_ara::collector gf_ara::per)
  add_test(NAME gf_dem_lite_smoke COMMAND gf_dem_lite_smoke)
endif()
