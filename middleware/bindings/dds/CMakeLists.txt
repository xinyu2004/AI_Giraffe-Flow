# Eclipse CycloneDDS is the default DDS vendor when GF_WITH_DDS=ON.
# Offline CI: GF_DDS_BACKEND=stub (in-process TopicBus).
# Real backend: tree present + GF_DDS_BACKEND=cyclone → link ddsc + idlc GfBlob.

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
set(_gf_dds_use_cyclone FALSE)

if(GF_DDS_BACKEND STREQUAL "cyclone")
  if(EXISTS "${_gf_cdds}/CMakeLists.txt" OR TARGET CycloneDDS::ddsc OR TARGET ddsc)
    set(_gf_dds_use_cyclone TRUE)
  else()
    message(WARNING
      "Giraffe Flow: GF_DDS_BACKEND=cyclone but CycloneDDS not found under "
      "${_gf_cdds}; falling back to stub. Run: bash scripts/bootstrap_deps.sh")
  endif()
endif()

if(_gf_dds_use_cyclone)
  if(TARGET CycloneDDS::ddsc)
    target_link_libraries(gf_ara_com_dds PUBLIC CycloneDDS::ddsc)
  elseif(TARGET ddsc)
    target_link_libraries(gf_ara_com_dds PUBLIC ddsc)
  endif()

  # Generate GfBlob type support with idlc (built with CycloneDDS).
  set(_gf_blob_idl "${CMAKE_CURRENT_SOURCE_DIR}/idl/GfBlob.idl")
  set(_gf_blob_out_dir "${CMAKE_CURRENT_BINARY_DIR}/generated")
  file(MAKE_DIRECTORY "${_gf_blob_out_dir}")
  set(_gf_blob_c "${_gf_blob_out_dir}/GfBlob.c")
  set(_gf_blob_h "${_gf_blob_out_dir}/GfBlob.h")

  if(TARGET idlc)
    set(_gf_idlc_exe "$<TARGET_FILE:idlc>")
    add_custom_command(
      OUTPUT "${_gf_blob_c}" "${_gf_blob_h}"
      COMMAND ${CMAKE_COMMAND} -E make_directory "${_gf_blob_out_dir}"
      COMMAND ${_gf_idlc_exe} -o "${_gf_blob_out_dir}" "${_gf_blob_idl}"
      DEPENDS idlc "${_gf_blob_idl}"
      COMMENT "idlc GfBlob.idl → CycloneDDS type support"
      VERBATIM
    )
  else()
    find_program(_gf_idlc_prog idlc)
    if(NOT _gf_idlc_prog)
      message(FATAL_ERROR
        "GF_DDS_BACKEND=cyclone requires idlc (build CycloneDDS with BUILD_IDLC=ON)")
    endif()
    add_custom_command(
      OUTPUT "${_gf_blob_c}" "${_gf_blob_h}"
      COMMAND ${CMAKE_COMMAND} -E make_directory "${_gf_blob_out_dir}"
      COMMAND "${_gf_idlc_prog}" -o "${_gf_blob_out_dir}" "${_gf_blob_idl}"
      DEPENDS "${_gf_blob_idl}"
      COMMENT "idlc GfBlob.idl → CycloneDDS type support"
      VERBATIM
    )
  endif()

  target_sources(gf_ara_com_dds PRIVATE
    src/cyclone_transport.cpp
    "${_gf_blob_c}"
  )
  target_include_directories(gf_ara_com_dds PUBLIC
    $<BUILD_INTERFACE:${_gf_blob_out_dir}>
  )
  # idlc may emit C; ensure C language enabled
  enable_language(C)
  set_source_files_properties("${_gf_blob_c}" PROPERTIES LANGUAGE C)

  target_compile_definitions(gf_ara_com_dds PUBLIC GF_DDS_USE_CYCLONEDDS=1)
  message(STATUS "Giraffe Flow: DDS backend=cyclone (real ddsc pub/sub)")
else()
  message(STATUS "Giraffe Flow: DDS backend=stub (in-process)")
endif()

if(GF_BUILD_TESTS)
  add_executable(gf_dds_binding_smoke tests/smoke_binding.cpp)
  target_link_libraries(gf_dds_binding_smoke PRIVATE gf_ara::com_dds)
  add_test(NAME gf_dds_binding_smoke COMMAND gf_dds_binding_smoke)
endif()
