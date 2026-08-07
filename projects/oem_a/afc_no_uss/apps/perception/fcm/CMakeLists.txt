# perception.fcm — SIL stub + optional frame tip / ORT (P3-5 wave B)

option(GF_WITH_ONNX "Link onnxruntime for GF_PERCEPTION_BACKEND=onnx" OFF)

set(_fcm_srcs
  src/main.cpp
  src/frame_source.cpp
  src/detect_backend.cpp
)

add_executable(gf_perception_fcm ${_fcm_srcs})
target_include_directories(gf_perception_fcm PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/src")
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

if(GF_WITH_ONNX)
  target_compile_definitions(gf_perception_fcm PRIVATE GF_WITH_ONNX=1)
  find_path(ONNXRUNTIME_INCLUDE_DIR onnxruntime_cxx_api.h
    HINTS
      ENV ONNXRUNTIME_ROOT
      "${ONNXRUNTIME_ROOT}"
    PATH_SUFFIXES include
  )
  find_library(ONNXRUNTIME_LIBRARY onnxruntime
    HINTS
      ENV ONNXRUNTIME_ROOT
      "${ONNXRUNTIME_ROOT}"
    PATH_SUFFIXES lib lib64
  )
  if(ONNXRUNTIME_INCLUDE_DIR AND ONNXRUNTIME_LIBRARY)
    target_include_directories(gf_perception_fcm PRIVATE "${ONNXRUNTIME_INCLUDE_DIR}")
    target_link_libraries(gf_perception_fcm PRIVATE "${ONNXRUNTIME_LIBRARY}")
    message(STATUS "gf_perception_fcm: ORT enabled (${ONNXRUNTIME_LIBRARY})")
  else()
    message(WARNING
      "GF_WITH_ONNX=ON but onnxruntime not found "
      "(set ONNXRUNTIME_ROOT). Building with pixel-heuristic fallback only.")
  endif()
endif()
