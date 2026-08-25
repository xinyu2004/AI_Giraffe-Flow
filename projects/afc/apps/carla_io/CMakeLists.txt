cmake_minimum_required(VERSION 3.16)
add_executable(gf_carla_io src/main.cpp)
target_link_libraries(gf_carla_io PRIVATE gf_channel::channel)
target_compile_features(gf_carla_io PRIVATE cxx_std_17)
set_target_properties(gf_carla_io PROPERTIES
  BUILD_RPATH_USE_ORIGIN TRUE
  INSTALL_RPATH "$ORIGIN/../lib"
  BUILD_RPATH "${CMAKE_BINARY_DIR}/lib;$ORIGIN/../lib"
)
