add_library(gf_ara_sm STATIC
  src/state_client.cpp
)
add_library(gf_ara::sm ALIAS gf_ara_sm)

target_include_directories(gf_ara_sm PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_link_libraries(gf_ara_sm PUBLIC gf_ara::core gf_ara::log)

if(GF_BUILD_TESTS)
  add_executable(gf_sm_fg_smoke testcases/smoke_fg.cpp)
  target_link_libraries(gf_sm_fg_smoke PRIVATE gf_ara::sm)
  add_test(NAME gf_sm_fg_smoke COMMAND gf_sm_fg_smoke)
endif()
