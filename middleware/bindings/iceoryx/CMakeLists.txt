add_library(gf_ara_com_iceoryx STATIC
  src/status.cpp
  src/runtime.cpp
)
add_library(gf_ara::com_iceoryx ALIAS gf_ara_com_iceoryx)

target_include_directories(gf_ara_com_iceoryx PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

target_link_libraries(gf_ara_com_iceoryx
  PUBLIC
    gf_ara::com
    iceoryx_posh
)

if(GF_BUILD_TESTS)
  add_executable(gf_iox_binding_smoke tests/smoke_binding.cpp)
  target_link_libraries(gf_iox_binding_smoke PRIVATE gf_ara::com_iceoryx)
  add_test(NAME gf_iox_binding_smoke COMMAND gf_iox_binding_smoke)
endif()
