# Process bring-up shared by SIL/HIL apps (FG + Offer/Running + PHM/Collector/Log).

add_library(gf_ara_runtime SHARED
  src/process_bringup.cpp
)
add_library(gf_ara::runtime ALIAS gf_ara_runtime)

target_include_directories(gf_ara_runtime PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_link_libraries(gf_ara_runtime PUBLIC
  gf_ara::exec
  gf_ara::phm
  gf_ara::sm
  gf_ara::collector
  gf_ara::log
  gf_ara::com
  gf_ara::per
)

# Prefer compose-frozen platform_tables.hpp (SKU builds set GF_GENERATED_DIR).
if(DEFINED GF_GENERATED_DIR AND EXISTS
   "${GF_GENERATED_DIR}/include/gf_gen/platform_tables.hpp")
  target_include_directories(gf_ara_runtime PRIVATE "${GF_GENERATED_DIR}/include")
  target_compile_definitions(gf_ara_runtime PRIVATE GF_HAS_PLATFORM_TABLES=1)
endif()
if(DEFINED GF_GENERATED_DIR AND EXISTS
   "${GF_GENERATED_DIR}/include/gf_gen/collector_config.hpp")
  target_include_directories(gf_ara_runtime PRIVATE "${GF_GENERATED_DIR}/include")
  target_compile_definitions(gf_ara_runtime PRIVATE GF_HAS_COLLECTOR_CONFIG=1)
endif()
if(DEFINED GF_GENERATED_DIR AND EXISTS
   "${GF_GENERATED_DIR}/include/gf_gen/bounds_config.hpp")
  target_include_directories(gf_ara_runtime PRIVATE "${GF_GENERATED_DIR}/include")
  target_compile_definitions(gf_ara_runtime PRIVATE GF_HAS_BOUNDS_CONFIG=1)
endif()
