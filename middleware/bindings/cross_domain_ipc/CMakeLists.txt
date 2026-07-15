add_library(gf_ara_cross_domain_ipc STATIC
  src/transport.cpp
)
add_library(gf_ara::cross_domain_ipc ALIAS gf_ara_cross_domain_ipc)

target_include_directories(gf_ara_cross_domain_ipc PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

if(GF_BUILD_TESTS)
  add_executable(gf_cross_domain_ipc_smoke tests/smoke_transport.cpp)
  target_link_libraries(gf_cross_domain_ipc_smoke PRIVATE gf_ara::cross_domain_ipc)
  add_test(NAME gf_cross_domain_ipc_smoke COMMAND gf_cross_domain_ipc_smoke)
endif()
