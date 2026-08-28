# planning.driving — thin iceoryx shell + oct_gen + gf_octave_planning

set(_GF_PLAN_SOURCES src/main.cpp)

# Octave-generated headers are included from oct_gen/; .cpp optional later.
file(GLOB _GF_OCT_GEN_CPP CONFIGURE_DEPENDS
  "${CMAKE_CURRENT_SOURCE_DIR}/oct_gen/*.cpp"
)
list(APPEND _GF_PLAN_SOURCES ${_GF_OCT_GEN_CPP})

add_executable(gf_planning_driving ${_GF_PLAN_SOURCES})
target_link_libraries(gf_planning_driving PRIVATE
  gf_ara::com_iceoryx
  gf_ara::runtime
)
if(TARGET gf_octave_planning)
  target_link_libraries(gf_planning_driving PRIVATE gf_octave_planning)
  target_include_directories(gf_planning_driving PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/oct_gen"
  )
endif()
add_dependencies(gf_planning_driving iox-roudi)

if(NOT GF_USE_GENERATED)
  message(FATAL_ERROR "gf_planning_driving requires GF_USE_GENERATED=ON")
endif()
target_include_directories(gf_planning_driving PRIVATE
  "${GF_GENERATED_DIR}/include"
  "${CMAKE_CURRENT_SOURCE_DIR}/../../common/include"
)
target_compile_definitions(gf_planning_driving PRIVATE GF_USE_GENERATED=1)
