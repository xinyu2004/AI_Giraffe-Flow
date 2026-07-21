# Vehicle CAN gateway — SIL stub for adapter.vehicle_can_gateway
# X-track: platform_sil Offer→Running + PHM Alive

add_executable(gf_vehicle_can_gateway
  src/main.cpp
  ${CMAKE_SOURCE_DIR}/apps/common/src/platform_sil.cpp
)
target_include_directories(gf_vehicle_can_gateway PRIVATE
  ${CMAKE_SOURCE_DIR}/apps/common/include
)
target_link_libraries(gf_vehicle_can_gateway PRIVATE
  gf_ara::com_iceoryx
  gf_ara::exec
  gf_ara::phm
)
add_dependencies(gf_vehicle_can_gateway iox-roudi)

if(NOT GF_USE_GENERATED)
  message(FATAL_ERROR "gf_vehicle_can_gateway requires GF_USE_GENERATED=ON")
endif()
target_include_directories(gf_vehicle_can_gateway PRIVATE "${GF_GENERATED_DIR}/include")
target_compile_definitions(gf_vehicle_can_gateway PRIVATE GF_USE_GENERATED=1)
