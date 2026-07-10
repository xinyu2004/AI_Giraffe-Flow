add_executable(gf_demo_pipeline src/main.cpp)
target_include_directories(gf_demo_pipeline PRIVATE
  ${CMAKE_SOURCE_DIR}/apps/common/include
)
target_link_libraries(gf_demo_pipeline PRIVATE gf_ara::com_iceoryx)
add_dependencies(gf_demo_pipeline iox-roudi)

if(GF_USE_GENERATED)
  if(NOT EXISTS "${GF_GENERATED_DIR}/include/gf_gen/proxy/uss_zones_proxy.hpp")
    message(FATAL_ERROR
      "GF_USE_GENERATED=ON but missing ${GF_GENERATED_DIR}/include/gf_gen/proxy/uss_zones_proxy.hpp\n"
      "Run gf-codegen compose + generate into ${GF_GENERATED_DIR}")
  endif()
  target_include_directories(gf_demo_pipeline PRIVATE "${GF_GENERATED_DIR}/include")
  target_compile_definitions(gf_demo_pipeline PRIVATE GF_USE_GENERATED=1)
endif()
