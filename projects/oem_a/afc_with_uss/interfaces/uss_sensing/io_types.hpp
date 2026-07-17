// OEM A / AFC+USS — USS 语义接口（gf-config 导入用）
// 物理源：uss.dbc 仅 USS 信息（见 oem/uss.extract.yaml）；可为私有 CAN / SPI / GMT 模拟
// 不含车速：EgoMotion 只来自 vehicle_gateway
#pragma once

#include <cstdint>

namespace gf::demo::uss_sensing {

enum class UssZoneId : uint8_t {
  kFl = 0,
  kFrm = 1,
  kFr = 2,
  kRl = 3,
  kRrm = 4,
  kRr = 5,
  kCount = 6
};

struct UssZoneSample {
  uint8_t zone_id;
  uint8_t status;       // PDC_INFO.PDC_*_Status
  uint8_t distance_cm;  // P_USS_INFO*.USS_*_Dis [m] → cm
};

// W0 — 必连
struct UssZones {
  uint64_t timestamp_ns;
  uint8_t sys_status;   // PDC_INFO.PDC_Sys_Status
  uint8_t nearest_cm;
  uint16_t zone_mask;
  UssZoneSample zones[6];
};

// W1 — APA 车位/状态（传感器侧；非车辆 CAN）
struct ApaSlot {
  uint8_t slot_id;
  uint8_t slot_status;
  float length_m;
  float width_m;
};

struct ApaSlotList {
  uint64_t timestamp_ns;
  uint8_t apa_status;
  uint8_t slot_count;
  ApaSlot slots[3];
};

}  // namespace gf::demo::uss_sensing
