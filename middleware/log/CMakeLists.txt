add_library(gf_ara_log STATIC
  src/logger.cpp
)
add_library(gf_ara::log ALIAS gf_ara_log)

target_include_directories(gf_ara_log PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_link_libraries(gf_ara_log PUBLIC gf_ara::core)

if(GF_BUILD_TESTS)
  add_executable(gf_log_smoke testcases/smoke_log.cpp)
  target_link_libraries(gf_log_smoke PRIVATE gf_ara::log)
  add_test(NAME gf_log_smoke COMMAND gf_log_smoke)
endif()
