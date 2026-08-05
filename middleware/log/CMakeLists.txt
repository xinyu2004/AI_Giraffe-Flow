add_library(gf_ara_log STATIC
  src/logger.cpp
  src/dlt_sink.cpp
)
add_library(gf_ara::log ALIAS gf_ara_log)

target_include_directories(gf_ara_log PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_link_libraries(gf_ara_log PUBLIC gf_ara::core)

if(GF_DLT_FOUND AND TARGET dlt)
  target_compile_definitions(gf_ara_log PUBLIC GF_HAVE_DLT=1)
  target_link_libraries(gf_ara_log PUBLIC dlt)
  if(TARGET dlt-daemon)
    add_dependencies(gf_ara_log dlt-daemon)
  endif()
  if(TARGET dlt-receive)
    add_dependencies(gf_ara_log dlt-receive)
  endif()
  message(STATUS "Giraffe Flow: gf_ara::log linked to COVESA libdlt")
else()
  target_compile_definitions(gf_ara_log PUBLIC GF_HAVE_DLT=0)
endif()

add_executable(gf_dlt_log src/dlt_log_main.cpp)
target_link_libraries(gf_dlt_log PRIVATE gf_ara::log)

if(GF_BUILD_TESTS)
  add_executable(gf_log_smoke testcases/smoke_log.cpp)
  target_link_libraries(gf_log_smoke PRIVATE gf_ara::log)
  add_test(NAME gf_log_smoke COMMAND gf_log_smoke)
endif()
