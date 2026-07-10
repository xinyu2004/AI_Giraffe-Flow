add_executable(gf_uss_feed src/main.cpp)
target_include_directories(gf_uss_feed PRIVATE
  ${CMAKE_SOURCE_DIR}/apps/common/include
)
target_link_libraries(gf_uss_feed PRIVATE gf_ara::com_iceoryx)
add_dependencies(gf_uss_feed iox-roudi)

if(GF_USE_GENERATED)
  if(NOT EXISTS "${GF_GENERATED_DIR}/include/gf_gen/skeleton/uss_zones_skeleton.hpp")
    message(FATAL_ERROR
      "GF_USE_GENERATED=ON but missing ${GF_GENERATED_DIR}/include/gf_gen/skeleton/uss_zones_skeleton.hpp\n"
      "Run:\n"
      "  gf-codegen compose --project projects/oem_a/afc_with_uss/project.yaml\n"
      "  gf-codegen generate projects/oem_a/afc_with_uss/gf.sor.json --out generated/")
  endif()
  target_include_directories(gf_uss_feed PRIVATE "${GF_GENERATED_DIR}/include")
  target_compile_definitions(gf_uss_feed PRIVATE GF_USE_GENERATED=1)
endif()
