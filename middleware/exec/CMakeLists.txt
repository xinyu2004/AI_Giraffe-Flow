add_library(gf_ara_exec STATIC
  src/execution_client.cpp
  src/execution_manager.cpp
  src/em_daemon.cpp
)
add_library(gf_ara::exec ALIAS gf_ara_exec)

target_include_directories(gf_ara_exec PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_link_libraries(gf_ara_exec PUBLIC gf_ara::core gf::osal gf_ara::log)

add_executable(gf_em_daemon src/em_daemon_main.cpp)
target_link_libraries(gf_em_daemon PRIVATE gf_ara::exec)

if(GF_BUILD_TESTS)
  add_executable(gf_exec_smoke testcases/smoke_exec.cpp)
  target_link_libraries(gf_exec_smoke PRIVATE gf_ara::exec)
  add_test(NAME gf_exec_smoke COMMAND gf_exec_smoke)

  add_executable(gf_exec_em_smoke testcases/smoke_em.cpp)
  target_link_libraries(gf_exec_em_smoke PRIVATE gf_ara::exec)
  add_test(NAME gf_exec_em_smoke COMMAND gf_exec_em_smoke)

  add_executable(gf_em_child_stub testcases/em_child_stub.cpp)
  target_link_libraries(gf_em_child_stub PRIVATE gf_ara::exec)

  add_executable(gf_em_daemon_smoke testcases/smoke_em_daemon.cpp)
  target_link_libraries(gf_em_daemon_smoke PRIVATE gf_ara::exec)
  add_dependencies(gf_em_daemon_smoke gf_em_child_stub)
  add_test(NAME gf_em_daemon_smoke COMMAND gf_em_daemon_smoke)
endif()
