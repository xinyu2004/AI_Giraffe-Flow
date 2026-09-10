add_executable(gf_perception_surround src/main.cpp)
target_link_libraries(gf_perception_surround PRIVATE
  gf_ara::com_iceoryx
  gf_ara::runtime
  gf_channel::channel
)
add_dependencies(gf_perception_surround iox-roudi)
if(NOT GF_USE_GENERATED)
  message(FATAL_ERROR "gf_perception_surround requires GF_USE_GENERATED=ON")
endif()
target_include_directories(gf_perception_surround PRIVATE "${GF_GENERATED_DIR}/include")
target_compile_definitions(gf_perception_surround PRIVATE GF_USE_GENERATED=1)
