add_library(gf_channel SHARED
  src/gf_channel.cpp
)
add_library(gf_channel::channel ALIAS gf_channel)

target_include_directories(gf_channel PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

target_compile_features(gf_channel PUBLIC cxx_std_17)

if(UNIX AND NOT APPLE)
  target_link_libraries(gf_channel PUBLIC rt)
endif()

set_target_properties(gf_channel PROPERTIES
  OUTPUT_NAME gf_channel
  VERSION 0.1.0
  SOVERSION 0
  BUILD_RPATH_USE_ORIGIN TRUE
  INSTALL_RPATH "$ORIGIN"
  BUILD_RPATH "${CMAKE_BINARY_DIR}/lib;$ORIGIN"
)

if(GF_BUILD_TESTS)
  add_executable(gf_channel_smoke testcases/smoke_gf_channel.cpp)
  target_link_libraries(gf_channel_smoke PRIVATE gf_channel::channel)
  add_test(NAME gf_channel_smoke COMMAND gf_channel_smoke)
endif()
