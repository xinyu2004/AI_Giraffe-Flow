# planning.driving — SIL stub + platform_sil (exec/phm + fault inject)

add_executable(gf_planning_driving
  src/main.cpp
  ${CMAKE_SOURCE_DIR}/apps/common/src/platform_sil.cpp
)
target_include_directories(gf_planning_driving PRIVATE
  ${CMAKE_SOURCE_DIR}/apps/common/include
)
target_link_libraries(gf_planning_driving PRIVATE
  gf_ara::com_iceoryx
  gf_ara::exec
  gf_ara::phm
)
add_dependencies(gf_planning_driving iox-roudi)

if(NOT GF_USE_GENERATED)
  message(FATAL_ERROR "gf_planning_driving requires GF_USE_GENERATED=ON")
endif()
target_include_directories(gf_planning_driving PRIVATE "${GF_GENERATED_DIR}/include")
target_compile_definitions(gf_planning_driving PRIVATE GF_USE_GENERATED=1)
