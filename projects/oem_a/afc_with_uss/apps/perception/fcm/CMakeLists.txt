# perception.fcm — SIL stub + process bring-up (exec/phm)

add_executable(gf_perception_fcm
  src/main.cpp
)
target_link_libraries(gf_perception_fcm PRIVATE
  gf_ara::com_iceoryx
  gf_ara::runtime
)
add_dependencies(gf_perception_fcm iox-roudi)

if(NOT GF_USE_GENERATED)
  message(FATAL_ERROR "gf_perception_fcm requires GF_USE_GENERATED=ON")
endif()
target_include_directories(gf_perception_fcm PRIVATE "${GF_GENERATED_DIR}/include")
target_compile_definitions(gf_perception_fcm PRIVATE GF_USE_GENERATED=1)
