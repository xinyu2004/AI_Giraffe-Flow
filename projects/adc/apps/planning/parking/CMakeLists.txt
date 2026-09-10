add_executable(gf_planning_parking src/main.cpp)
target_link_libraries(gf_planning_parking PRIVATE
  gf_ara::com_iceoryx
  gf_ara::runtime
  gf_octave_planning
)
add_dependencies(gf_planning_parking iox-roudi)
if(NOT GF_USE_GENERATED)
  message(FATAL_ERROR "gf_planning_parking requires GF_USE_GENERATED=ON")
endif()
target_include_directories(gf_planning_parking PRIVATE
  "${GF_GENERATED_DIR}/include"
  "${CMAKE_CURRENT_SOURCE_DIR}/oct_gen"
)
target_compile_definitions(gf_planning_parking PRIVATE GF_USE_GENERATED=1)
