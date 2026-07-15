add_library(gf_ara_diag STATIC
  src/doip_stack.cpp
)
add_library(gf_ara::diag ALIAS gf_ara_diag)

target_include_directories(gf_ara_diag PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_link_libraries(gf_ara_diag PUBLIC gf_ara::core)

if(GF_BUILD_TESTS)
  add_executable(gf_diag_doip_smoke tests/smoke_doip.cpp)
  target_link_libraries(gf_diag_doip_smoke PRIVATE gf_ara::diag)
  add_test(NAME gf_diag_doip_smoke COMMAND gf_diag_doip_smoke)
endif()
