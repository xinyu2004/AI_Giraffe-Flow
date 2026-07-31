add_library(gf_ara_tsync STATIC
  src/time_sync.cpp
)
add_library(gf_ara::tsync ALIAS gf_ara_tsync)

target_include_directories(gf_ara_tsync PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_link_libraries(gf_ara_tsync PUBLIC gf_ara::core gf::osal)

if(GF_BUILD_TESTS)
  add_executable(gf_tsync_smoke testcases/smoke_tsync.cpp)
  target_link_libraries(gf_tsync_smoke PRIVATE gf_ara::tsync)
  add_test(NAME gf_tsync_smoke COMMAND gf_tsync_smoke)
endif()
