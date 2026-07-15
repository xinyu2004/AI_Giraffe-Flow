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
option(GF_WITH_SOMEIP "Build SOME/IP binding when implemented" OFF)
option(GF_WITH_DDS "Build DDS binding when implemented" OFF)
option(GF_WITH_CROSS_DOMAIN_IPC "Build cross_domain_ipc binding when implemented" OFF)

set(GF_GENERATED_DIR "${CMAKE_SOURCE_DIR}/generated" CACHE PATH "gf-codegen --out directory")
set(GF_SKU_CMAKE "" CACHE FILEPATH "SKU fragment from compose (generated/gf_build.cmake)")

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")

# Apply SKU before Dependencies so GF_WITH_* drive third-party fetch.
if(GF_SKU_CMAKE STREQUAL "")
  set(GF_SKU_CMAKE "${CMAKE_SOURCE_DIR}/cmake/profiles/desktop_default.cmake")
  message(STATUS "Giraffe Flow: no GF_SKU_CMAKE; using ${GF_SKU_CMAKE}")
endif()
if(EXISTS "${GF_SKU_CMAKE}")
  include("${GF_SKU_CMAKE}")
  message(STATUS "Giraffe Flow: SKU ${GF_SKU_VARIANT} from ${GF_SKU_CMAKE}")
else()
  message(WARNING "Giraffe Flow: GF_SKU_CMAKE not found: ${GF_SKU_CMAKE}")
endif()

# Explicit force-off wins over SKU (e.g. aarch64 OSAL-only link smoke).
if(GF_FORCE_NO_ICEORYX)
  set(GF_WITH_ICEORYX OFF CACHE BOOL "Build iceoryx binding" FORCE)
  message(STATUS "Giraffe Flow: GF_FORCE_NO_ICEORYX=ON → iceoryx OFF")
endif()

include(Dependencies)

if(GF_BUILD_TESTS)
  enable_testing()
endif()

include(GfModules)

message(STATUS "Giraffe Flow: GF_WITH_ICEORYX=${GF_WITH_ICEORYX}")
message(STATUS "Giraffe Flow: GF_USE_GENERATED=${GF_USE_GENERATED}")
message(STATUS "Giraffe Flow: GF_BUILD_TESTS=${GF_BUILD_TESTS}")
message(STATUS "Giraffe Flow: GF_APPS=${GF_APPS}")
