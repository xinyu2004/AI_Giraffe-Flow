add_library(gf_ara_per STATIC
  src/key_value_storage.cpp
)
add_library(gf_ara::per ALIAS gf_ara_per)

target_include_directories(gf_ara_per PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_link_libraries(gf_ara_per PUBLIC gf_ara::core)

if(GF_BUILD_TESTS)
  add_executable(gf_per_smoke testcases/smoke_per.cpp)
  target_link_libraries(gf_per_smoke PRIVATE gf_ara::per)
  add_test(NAME gf_per_smoke COMMAND gf_per_smoke)
endif()
