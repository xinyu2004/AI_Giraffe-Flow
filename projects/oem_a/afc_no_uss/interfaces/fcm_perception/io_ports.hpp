// FCM 感知 — gf-config 对接端口（粗粒度 / 整包）
// 字段细节见 100_dbc/FCM_hpp/Perception_{In,Out}_messages.h（金样，不在此展开）
// 画布上一条边 = 一整包协议，取代线下「对 Perception_In / MESSAGE_Out」会议
#pragma once

#include <cstdint>

namespace gf::demo::fcm_perception {

// 车辆/AEB 周期输入整包（vendor: Perception_In_St）
struct Perception_In_St {
  uint64_t timestamp_ns;
  uint32_t ipc_frame_counter;
  uint8_t gear;
  float vehicle_speed;
  float yaw_rate;
  // 其余字段见 vendor 头；compose/运行时以金样为准
  uint8_t _vendor_payload_opaque[1];
};

// 初始化/标定整包（可选端口）
struct Perception_Init_St {
  uint64_t timestamp_ns;
  uint8_t _vendor_payload_opaque[1];
};

// 感知输出总包（vendor: Perception_MESSAGE_Out_St）
struct Perception_MESSAGE_Out_St {
  uint64_t timestamp_ns;
  uint8_t dyn_obj_count;
  uint8_t static_obj_count;
  uint8_t _vendor_payload_opaque[1];
};

}  // namespace gf::demo::fcm_perception
