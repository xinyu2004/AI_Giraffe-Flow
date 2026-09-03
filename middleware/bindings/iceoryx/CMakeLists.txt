add_library(gf_ara_com_iceoryx SHARED
  src/status.cpp
  src/runtime.cpp
)
add_library(gf_ara::com_iceoryx ALIAS gf_ara_com_iceoryx)

target_include_directories(gf_ara_com_iceoryx PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

target_link_libraries(gf_ara_com_iceoryx
  PUBLIC
    gf_ara::com
    iceoryx_posh
)

if(GF_BUILD_TESTS)
  add_executable(gf_iox_binding_smoke testcases/smoke_binding.cpp)
  target_link_libraries(gf_iox_binding_smoke PRIVATE gf_ara::com_iceoryx)
  add_test(NAME gf_iox_binding_smoke COMMAND gf_iox_binding_smoke)

  add_executable(gf_iox_smoke_pub testcases/smoke_pub.cpp)
  target_include_directories(gf_iox_smoke_pub PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/testcases)
  target_link_libraries(gf_iox_smoke_pub PRIVATE gf_ara::com_iceoryx)
  add_dependencies(gf_iox_smoke_pub iox-roudi)

  add_executable(gf_iox_smoke_sub testcases/smoke_sub.cpp)
  target_include_directories(gf_iox_smoke_sub PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/testcases)
  target_link_libraries(gf_iox_smoke_sub PRIVATE gf_ara::com_iceoryx)
  add_dependencies(gf_iox_smoke_sub iox-roudi)

  add_test(
    NAME gf_iox_pubsub_smoke
    COMMAND bash "${CMAKE_CURRENT_SOURCE_DIR}/testcases/run_iox_pubsub.sh"
  )
  set_tests_properties(gf_iox_pubsub_smoke PROPERTIES
    ENVIRONMENT "GF_BUILD_DIR=${CMAKE_BINARY_DIR}"
  )
endif()
