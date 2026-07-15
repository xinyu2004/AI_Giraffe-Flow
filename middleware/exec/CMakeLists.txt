add_library(gf_ara_exec STATIC
  src/execution_client.cpp
)
add_library(gf_ara::exec ALIAS gf_ara_exec)

target_include_directories(gf_ara_exec PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_link_libraries(gf_ara_exec PUBLIC gf_ara::core)

if(GF_BUILD_TESTS)
  add_executable(gf_exec_smoke tests/smoke_exec.cpp)
  target_link_libraries(gf_exec_smoke PRIVATE gf_ara::exec)
  add_test(NAME gf_exec_smoke COMMAND gf_exec_smoke)
endif()
