// OEM A / AFC+USS — 外仓交付的 USS 接口落盘（与共享基线同形；项目内持有副本便于审计/封板）
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
  uint8_t status;
  uint8_t distance_cm;
};

struct UssZones {
  uint64_t timestamp_ns;
  uint8_t sys_status;
  uint8_t nearest_cm;
  uint16_t zone_mask;
  UssZoneSample zones[6];
};

}  // namespace gf::demo::uss_sensing
