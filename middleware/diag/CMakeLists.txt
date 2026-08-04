add_library(gf_ara_diag STATIC
  src/doip_stack.cpp
  src/doip_proto.cpp
  src/doip_session.cpp
  src/uds_dispatcher.cpp
)
add_library(gf_ara::diag ALIAS gf_ara_diag)

target_include_directories(gf_ara_diag PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_link_libraries(gf_ara_diag PUBLIC gf_ara::core gf_ara::collector ${CMAKE_DL_LIBS})

# SIL security plugin (.so) — OEM replaces via diag.yaml path
add_library(gf_diag_sec_sil_stub SHARED plugins/sil_sec_stub.c)
target_include_directories(gf_diag_sec_sil_stub PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/include)
set_target_properties(gf_diag_sec_sil_stub PROPERTIES
  OUTPUT_NAME "gf_diag_sec_sil_stub"
  LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}")

# gf_doip_ota_server + session smoke registered in cmake/GfModules.cmake after ucm/sm/collector.

if(GF_BUILD_TESTS)
  add_executable(gf_diag_doip_smoke testcases/smoke_doip.cpp)
  target_link_libraries(gf_diag_doip_smoke PRIVATE gf_ara::diag)
  add_test(NAME gf_diag_doip_smoke COMMAND gf_diag_doip_smoke)

  add_executable(gf_uds_nrc_smoke testcases/smoke_uds_nrc.cpp)
  target_link_libraries(gf_uds_nrc_smoke PRIVATE gf_ara::diag)
  add_dependencies(gf_uds_nrc_smoke gf_diag_sec_sil_stub)
  add_test(NAME gf_uds_nrc_smoke COMMAND gf_uds_nrc_smoke)
endif()
