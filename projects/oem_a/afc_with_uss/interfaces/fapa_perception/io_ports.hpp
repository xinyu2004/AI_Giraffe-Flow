// FAPA 泊车感知 — gf-config 对接端口（粗粒度 / 整包）
// 字段细节见 100_dbc/FAPA_hpp/Perception_{in,out}_messages.h
#pragma once

#include <cstdint>

namespace gf::demo::fapa_perception {

// 100ms APA/AVM 模式与门控
struct IPC_CanInfo_100ms_St {
  uint64_t timestamp_ns;
  uint8_t apa_on_off;
  uint8_t apa_mode;
  uint8_t apa_status;
  uint8_t avm_on_off;
  uint8_t avm_mode;
};

// 20ms 车速 / 轮速 / 横摆（≈ EgoMotion 同源，形状跟 vendor）
struct IPC_CanInfo_20ms_St {
  uint64_t timestamp_ns;
  float vehicle_speed;
  float yaw_rate;
  float wheel_fl;
  float wheel_fr;
  float wheel_rl;
  float wheel_rr;
};

// 10ms 转向 / 档位 / 同步位姿
struct IPC_CanInfo_10ms_St {
  uint64_t timestamp_ns;
  float steer_angle;
  uint8_t gear;
  float sync_x;
  float sync_y;
  float sync_angle;
};

// 泊车感知输出总包（vendor: IPC_ADC_Perception_Out_St）
struct IPC_ADC_Perception_Out_St {
  uint64_t timestamp_ns;
  uint64_t frame_id;
  uint8_t apa_on_off;
  uint8_t apa_mode;
  uint8_t slot_count;
  uint8_t obstacle_count;
  uint8_t _vendor_payload_opaque[1];
};

}  // namespace gf::demo::fapa_perception
