# Process bring-up shared by SIL/HIL apps (FG + Offer/Running + PHM/Collector/Log).

add_library(gf_ara_runtime STATIC
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
)
