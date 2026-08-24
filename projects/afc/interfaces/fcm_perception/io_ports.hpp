// FCM 感知 — gf-config 对接
// Out 金样：同目录 Perception_Out_messages.h（wiring 一并解析）
// In/Init：此处粗端口；In 金样依赖 CamCalib，暂未入库
#pragma once

#include <cstdint>

namespace gf::demo::fcm_perception {

// 车辆/AEB 周期输入整包（vendor: Perception_In_St；金样待 CamCalib）
struct Perception_In_St {
  uint64_t timestamp_ns;
  uint32_t ipc_frame_counter;
  uint8_t gear;
  float vehicle_speed;
  float yaw_rate;
  uint8_t _vendor_payload_opaque[1];
};

// 初始化/标定整包（可选端口）
struct Perception_Init_St {
  uint64_t timestamp_ns;
  uint8_t _vendor_payload_opaque[1];
};

}  // namespace gf::demo::fcm_perception
