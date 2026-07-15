add_library(gf_ara_phm STATIC
  src/supervised_entity.cpp
)
add_library(gf_ara::phm ALIAS gf_ara_phm)

target_include_directories(gf_ara_phm PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_link_libraries(gf_ara_phm PUBLIC gf::osal gf_ara::core)

if(GF_BUILD_TESTS)
  add_executable(gf_phm_alive_deadline_smoke tests/smoke_alive_deadline.cpp)
  target_link_libraries(gf_phm_alive_deadline_smoke PRIVATE gf_ara::phm gf_ara::exec)
  add_test(NAME gf_phm_alive_deadline_smoke COMMAND gf_phm_alive_deadline_smoke)
endif()
