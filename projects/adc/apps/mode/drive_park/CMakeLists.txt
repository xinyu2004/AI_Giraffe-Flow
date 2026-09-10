# Mode Manager — VehicleMode (Driving / SpotSearch / Parking)
add_executable(gf_mode_drive_park src/main.cpp)
target_link_libraries(gf_mode_drive_park PRIVATE
  gf_ara::com_iceoryx
  gf_ara::runtime
  gf_ara::sm
  gf_channel::channel
)
add_dependencies(gf_mode_drive_park iox-roudi)
if(NOT GF_USE_GENERATED)
  message(FATAL_ERROR "gf_mode_drive_park requires GF_USE_GENERATED=ON")
endif()
target_include_directories(gf_mode_drive_park PRIVATE "${GF_GENERATED_DIR}/include")
target_compile_definitions(gf_mode_drive_park PRIVATE GF_USE_GENERATED=1)
