# Reference AP gateway for ap_mcu_cp (desktop pairs with cp_ipc_peer).
set(GF_MCU_IO_TYPES_DIR
  "${CMAKE_SOURCE_DIR}/projects/oem_b/adc_full/interfaces/mcu_cp_gateway"
  CACHE PATH "io_types.hpp for mcu_cp_gateway")

add_executable(gf_mcu_cp_gateway src/main.cpp)
target_include_directories(gf_mcu_cp_gateway PRIVATE
  "${GF_MCU_IO_TYPES_DIR}"
)
target_link_libraries(gf_mcu_cp_gateway PRIVATE gf_ara::cross_domain_ipc)
