add_library(gf_osal STATIC
  src/posix/clock.cpp
  src/posix/thread.cpp
)
add_library(gf::osal ALIAS gf_osal)

target_include_directories(gf_osal PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

if(GF_BUILD_TESTS)
  add_executable(gf_osal_smoke tests/smoke_osal.cpp)
  target_link_libraries(gf_osal_smoke PRIVATE gf::osal)
  add_test(NAME gf_osal_smoke COMMAND gf_osal_smoke)
endif()
