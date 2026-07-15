# Desktop AUTOSAR CP IPC peer simulator (no real MCU).
set(GF_MCU_IO_TYPES_DIR
  "${CMAKE_SOURCE_DIR}/projects/oem_b/adc_full/interfaces/mcu_cp_gateway"
  CACHE PATH "io_types.hpp for mcu_cp_gateway / cp_ipc_peer")

add_executable(gf_cp_ipc_peer src/main.cpp)
target_include_directories(gf_cp_ipc_peer PRIVATE
  "${GF_MCU_IO_TYPES_DIR}"
)
target_link_libraries(gf_cp_ipc_peer PRIVATE gf_ara::cross_domain_ipc)
