cmake_minimum_required(VERSION 3.16)
add_executable(gf_frame_colorbar src/main.cpp)
target_link_libraries(gf_frame_colorbar PRIVATE gf_channel::channel)
target_compile_features(gf_frame_colorbar PRIVATE cxx_std_17)
set_target_properties(gf_frame_colorbar PROPERTIES
  BUILD_RPATH_USE_ORIGIN TRUE
  INSTALL_RPATH "$ORIGIN/../lib"
  BUILD_RPATH "${CMAKE_BINARY_DIR}/lib;$ORIGIN/../lib"
)
