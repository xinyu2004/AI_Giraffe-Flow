add_library(gf_ara_ucm STATIC
  src/package_manager.cpp
)
add_library(gf_ara::ucm ALIAS gf_ara_ucm)

target_include_directories(gf_ara_ucm PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_link_libraries(gf_ara_ucm PUBLIC gf_ara::core)

if(GF_BUILD_TESTS)
  add_executable(gf_ucm_package_manager_smoke tests/smoke_package_manager.cpp)
  target_link_libraries(gf_ucm_package_manager_smoke PRIVATE gf_ara::ucm)
  add_test(NAME gf_ucm_package_manager_smoke COMMAND gf_ucm_package_manager_smoke)
endif()
