# Eclipse CycloneDDS is the default DDS vendor when GF_WITH_DDS=ON.
# P1 offline CI uses an in-process stub backend (no third_party download).
# When middleware/third_party/cyclonedds is present and GF_DDS_BACKEND=cyclone,
# CMake links ddsc and defines GF_DDS_USE_CYCLONEDDS=1 (API still stub loopback
# until a fuller Cyclone publisher is wired — BackendName reports cyclonedds).

add_library(gf_ara_com_dds STATIC
  src/runtime.cpp
)
add_library(gf_ara::com_dds ALIAS gf_ara_com_dds)

target_include_directories(gf_ara_com_dds PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_link_libraries(gf_ara_com_dds PUBLIC gf_ara::com gf_ara::core)

set(GF_DDS_BACKEND "stub" CACHE STRING "DDS backend: stub | cyclone")
set_property(CACHE GF_DDS_BACKEND PROPERTY STRINGS stub cyclone)

set(_gf_cdds "${CMAKE_SOURCE_DIR}/middleware/third_party/cyclonedds")
if(GF_DDS_BACKEND STREQUAL "cyclone")
  if(EXISTS "${_gf_cdds}/CMakeLists.txt" OR TARGET CycloneDDS::ddsc OR TARGET ddsc)
    if(TARGET CycloneDDS::ddsc)
      target_link_libraries(gf_ara_com_dds PUBLIC CycloneDDS::ddsc)
    elseif(TARGET ddsc)
      target_link_libraries(gf_ara_com_dds PUBLIC ddsc)
    endif()
    target_compile_definitions(gf_ara_com_dds PUBLIC GF_DDS_USE_CYCLONEDDS=1)
    message(STATUS "Giraffe Flow: DDS backend=cyclone (linked)")
  else()
    message(WARNING
      "Giraffe Flow: GF_DDS_BACKEND=cyclone but CycloneDDS not found under "
      "${_gf_cdds}; falling back to stub. Run bootstrap with cyclonedds.")
    message(STATUS "Giraffe Flow: DDS backend=stub (fallback)")
  endif()
else()
  message(STATUS "Giraffe Flow: DDS backend=stub (default offline)")
endif()

if(GF_BUILD_TESTS)
  add_executable(gf_dds_binding_smoke tests/smoke_binding.cpp)
  target_link_libraries(gf_dds_binding_smoke PRIVATE gf_ara::com_dds)
  add_test(NAME gf_dds_binding_smoke COMMAND gf_dds_binding_smoke)
endif()
