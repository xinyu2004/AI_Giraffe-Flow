# sensing.uss — SIL stub + platform_sil (exec/phm)

add_executable(gf_sensing_uss
  src/main.cpp
  ${CMAKE_SOURCE_DIR}/apps/common/src/platform_sil.cpp
)
target_include_directories(gf_sensing_uss PRIVATE
  ${CMAKE_SOURCE_DIR}/apps/common/include
)
target_link_libraries(gf_sensing_uss PRIVATE
  gf_ara::com_iceoryx
  gf_ara::exec
  gf_ara::phm
)
add_dependencies(gf_sensing_uss iox-roudi)

if(NOT GF_USE_GENERATED)
  message(FATAL_ERROR "gf_sensing_uss requires GF_USE_GENERATED=ON")
endif()
target_include_directories(gf_sensing_uss PRIVATE "${GF_GENERATED_DIR}/include")
target_compile_definitions(gf_sensing_uss PRIVATE GF_USE_GENERATED=1)
