# planning.driving_plus — multi-cam driving (FCM Out + FreespaceNear fuse)

set(_GF_PLAN_SOURCES src/main.cpp)

file(GLOB _GF_OCT_GEN_CPP CONFIGURE_DEPENDS
  "${CMAKE_CURRENT_SOURCE_DIR}/oct_gen/*.cpp"
)
list(APPEND _GF_PLAN_SOURCES ${_GF_OCT_GEN_CPP})

add_executable(gf_planning_driving_plus ${_GF_PLAN_SOURCES})
target_link_libraries(gf_planning_driving_plus PRIVATE
  gf_ara::com_iceoryx
  gf_ara::runtime
)
if(TARGET gf_octave_planning)
  target_link_libraries(gf_planning_driving_plus PRIVATE gf_octave_planning)
  target_include_directories(gf_planning_driving_plus PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/oct_gen"
  )
endif()
add_dependencies(gf_planning_driving_plus iox-roudi)

if(NOT GF_USE_GENERATED)
  message(FATAL_ERROR "gf_planning_driving_plus requires GF_USE_GENERATED=ON")
endif()
target_include_directories(gf_planning_driving_plus PRIVATE
  "${GF_GENERATED_DIR}/include"
  "${CMAKE_CURRENT_SOURCE_DIR}/src"
  "${CMAKE_CURRENT_SOURCE_DIR}/../../common/include"
)
target_compile_definitions(gf_planning_driving_plus PRIVATE GF_USE_GENERATED=1)
