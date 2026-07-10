add_library(gf_ara_core INTERFACE)
add_library(gf_ara::core ALIAS gf_ara_core)

target_include_directories(gf_ara_core INTERFACE
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

if(GF_BUILD_TESTS)
  add_executable(gf_core_smoke tests/smoke_result.cpp)
  target_link_libraries(gf_core_smoke PRIVATE gf_ara::core)
  add_test(NAME gf_core_smoke COMMAND gf_core_smoke)
endif()
