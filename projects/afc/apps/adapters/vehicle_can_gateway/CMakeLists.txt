# Vehicle CAN gateway — SIL stub for adapter.vehicle_can_gateway
# X-track: process bring-up Offer→Running + PHM Alive

add_executable(gf_vehicle_can_gateway
  src/main.cpp
)
target_link_libraries(gf_vehicle_can_gateway PRIVATE
  gf_ara::com_iceoryx
  gf_ara::runtime
  gf_channel::channel
)
add_dependencies(gf_vehicle_can_gateway iox-roudi)

if(NOT GF_USE_GENERATED)
  message(FATAL_ERROR "gf_vehicle_can_gateway requires GF_USE_GENERATED=ON")
endif()
target_include_directories(gf_vehicle_can_gateway PRIVATE "${GF_GENERATED_DIR}/include")
target_compile_definitions(gf_vehicle_can_gateway PRIVATE GF_USE_GENERATED=1)
set_target_properties(gf_vehicle_can_gateway PROPERTIES
  BUILD_RPATH_USE_ORIGIN TRUE
  INSTALL_RPATH "$ORIGIN/../lib"
  BUILD_RPATH "${CMAKE_BINARY_DIR}/lib;$ORIGIN/../lib"
)
