# frame_ingest — C++ resident video-contract ingress (freeze from frame_ingest_config.hpp)
cmake_minimum_required(VERSION 3.16)

add_executable(gf_frame_ingest src/main.cpp)

if(NOT GF_USE_GENERATED)
  message(FATAL_ERROR "gf_frame_ingest requires GF_USE_GENERATED=ON")
endif()

target_include_directories(gf_frame_ingest PRIVATE "${GF_GENERATED_DIR}/include")
target_compile_definitions(gf_frame_ingest PRIVATE GF_USE_GENERATED=1)
target_compile_features(gf_frame_ingest PRIVATE cxx_std_17)

if(TARGET gf_channel::channel)
  target_link_libraries(gf_frame_ingest PRIVATE gf_channel::channel)
else()
  message(FATAL_ERROR "gf_frame_ingest requires gf_channel::channel")
endif()

# Staged under runtime/bin → look for so in ../lib
set_target_properties(gf_frame_ingest PROPERTIES
  BUILD_RPATH_USE_ORIGIN TRUE
  INSTALL_RPATH "$ORIGIN/../lib"
  BUILD_RPATH "${CMAKE_BINARY_DIR}/lib;$ORIGIN/../lib"
)
