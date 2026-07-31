add_library(gf_ara_ucm STATIC
  src/package_manager.cpp
  src/ota_orchestrator.cpp
)
add_library(gf_ara::ucm ALIAS gf_ara_ucm)

target_include_directories(gf_ara_ucm PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

if(TARGET gf_ara_sm AND TARGET gf_ara_collector)
  target_link_libraries(gf_ara_ucm PUBLIC gf_ara::core gf_ara::sm gf_ara::collector)
else()
  message(FATAL_ERROR "Giraffe Flow: ucm requires sm + collector (SIL helpers)")
endif()

if(GF_BUILD_TESTS)
  add_executable(gf_ucm_package_manager_smoke testcases/smoke_package_manager.cpp)
  target_link_libraries(gf_ucm_package_manager_smoke PRIVATE gf_ara::ucm)
  add_test(NAME gf_ucm_package_manager_smoke COMMAND gf_ucm_package_manager_smoke)
endif()
