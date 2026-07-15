# vsomeip is P1-staged: linkable stub by default (no Boost download).
# Real COVESA vsomeip: set GF_SOMEIP_BACKEND=vsomeip after bootstrap (later).

add_library(gf_ara_com_someip STATIC
  src/runtime.cpp
)
add_library(gf_ara::com_someip ALIAS gf_ara_com_someip)

target_include_directories(gf_ara_com_someip PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_link_libraries(gf_ara_com_someip PUBLIC gf_ara::com gf_ara::core)

message(STATUS "Giraffe Flow: SOME/IP backend=stub (vsomeip staged)")

if(GF_BUILD_TESTS)
  add_executable(gf_someip_binding_smoke tests/smoke_binding.cpp)
  target_link_libraries(gf_someip_binding_smoke PRIVATE gf_ara::com_someip)
  add_test(NAME gf_someip_binding_smoke COMMAND gf_someip_binding_smoke)
endif()
