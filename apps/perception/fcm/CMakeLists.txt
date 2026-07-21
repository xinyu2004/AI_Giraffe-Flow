# perception.fcm — SIL stub + platform_sil (exec/phm)

add_executable(gf_perception_fcm
  src/main.cpp
  ${CMAKE_SOURCE_DIR}/apps/common/src/platform_sil.cpp
)
target_include_directories(gf_perception_fcm PRIVATE
  ${CMAKE_SOURCE_DIR}/apps/common/include
)
target_link_libraries(gf_perception_fcm PRIVATE
  gf_ara::com_iceoryx
  gf_ara::exec
  gf_ara::phm
)
add_dependencies(gf_perception_fcm iox-roudi)

if(NOT GF_USE_GENERATED)
  message(FATAL_ERROR "gf_perception_fcm requires GF_USE_GENERATED=ON")
endif()
target_include_directories(gf_perception_fcm PRIVATE "${GF_GENERATED_DIR}/include")
target_compile_definitions(gf_perception_fcm PRIVATE GF_USE_GENERATED=1)
