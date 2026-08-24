// 独立超声（USS）传感模块 — 实际项目中常为独立进程/团队
// 模块工程师只交本文件；连线由系统工程师在 wiring.yaml 配置

#pragma once

#include <cstdint>

namespace gf::demo::uss_sensing {

// --- provides：分区级超声摘要（不向 SOR 暴露逐探头原始帧）---

// 固定分区布局（示意 FL / FRM / FR / RL / RRM / RR）
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
  uint8_t zone_id;       // UssZoneId
  uint8_t status;        // 0=ok / 1=near / 2=blocked / 3=fault（示意）
  uint8_t distance_cm;   // 255 = invalid / no echo
};

struct UssZones {
  uint64_t timestamp_ns;
  uint8_t sys_status;
  uint8_t nearest_cm;    // 全区最近；255 = none
  uint16_t zone_mask;    // bit i 对应分区有有效回波
  UssZoneSample zones[6];
};

}  // namespace gf::demo::uss_sensing
