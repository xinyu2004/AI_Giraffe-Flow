cmake_minimum_required(VERSION 3.16)
project(AI_Giraffe_Flow VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

option(GF_BUILD_TESTS "Build middleware smoke tests" ON)
option(GF_WITH_ICEORYX "Build iceoryx binding (requires middleware/third_party/iceoryx)" OFF)
option(GF_FORCE_NO_ICEORYX "Do not auto-enable iceoryx when middleware/third_party is present" OFF)
option(GF_USE_GENERATED "Demo apps use gf-codegen Proxy/Skeleton under generated/" OFF)

set(GF_GENERATED_DIR "${CMAKE_SOURCE_DIR}/generated" CACHE PATH "gf-codegen --out directory")

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include(Dependencies)

if(GF_BUILD_TESTS)
  enable_testing()
endif()

add_subdirectory(middleware/core)
add_subdirectory(middleware/com)
add_subdirectory(middleware/osal)

if(GF_WITH_ICEORYX)
  add_subdirectory(middleware/bindings/iceoryx)
  add_subdirectory(apps/simulators/uss_feed)
  add_subdirectory(apps/demo_pipeline)
endif()

message(STATUS "Giraffe Flow: GF_WITH_ICEORYX=${GF_WITH_ICEORYX}")
message(STATUS "Giraffe Flow: GF_USE_GENERATED=${GF_USE_GENERATED}")
message(STATUS "Giraffe Flow: GF_BUILD_TESTS=${GF_BUILD_TESTS}")
