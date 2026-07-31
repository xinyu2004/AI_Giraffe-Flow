add_library(gf_ara_collector STATIC
  src/event_collector.cpp
)
add_library(gf_ara::collector ALIAS gf_ara_collector)

target_include_directories(gf_ara_collector PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_link_libraries(gf_ara_collector PUBLIC gf::osal gf_ara::core)

if(GF_BUILD_TESTS)
  add_executable(gf_collector_smoke testcases/smoke_collector.cpp)
  target_link_libraries(gf_collector_smoke PRIVATE gf_ara::collector)
  add_test(NAME gf_collector_smoke COMMAND gf_collector_smoke)
endif()
