add_library(gf_ara_com INTERFACE)
add_library(gf_ara::com ALIAS gf_ara_com)

target_include_directories(gf_ara_com INTERFACE
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

target_link_libraries(gf_ara_com INTERFACE gf_ara::core)

if(GF_BUILD_TESTS)
  add_executable(gf_com_loopback_smoke tests/smoke_loopback_event.cpp)
  target_link_libraries(gf_com_loopback_smoke PRIVATE gf_ara::com)
  add_test(NAME gf_com_loopback_smoke COMMAND gf_com_loopback_smoke)
endif()
