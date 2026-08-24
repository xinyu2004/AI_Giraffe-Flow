// 车辆 gateway — 粗端口：EgoMotion + 发给 FCM/FAPA 的整包输入
// 金样字段见 100_dbc/FCM_hpp、FAPA_hpp；此处供 gf-config 导入/连线
#pragma once

#include <cstdint>

namespace gf::demo::vehicle_gateway {

struct EgoMotion {
  uint64_t timestamp_ns;
  float speed_mps;
  float yaw_rate_degps;
  float steer_angle_deg;
  uint8_t gear;
};

// --- 与 fcm_perception::Perception_In_St 同名，供 gateway Provide ---
struct Perception_In_St {
  uint64_t timestamp_ns;
  uint32_t ipc_frame_counter;
  uint8_t gear;
  float vehicle_speed;
  float yaw_rate;
  uint8_t _vendor_payload_opaque[1];
};

struct IPC_CanInfo_100ms_St {
  uint64_t timestamp_ns;
  uint8_t apa_on_off;
  uint8_t apa_mode;
  uint8_t apa_status;
  uint8_t avm_on_off;
  uint8_t avm_mode;
};

struct IPC_CanInfo_20ms_St {
  uint64_t timestamp_ns;
  float vehicle_speed;
  float yaw_rate;
  float wheel_fl;
  float wheel_fr;
  float wheel_rl;
  float wheel_rr;
};

struct IPC_CanInfo_10ms_St {
  uint64_t timestamp_ns;
  float steer_angle;
  uint8_t gear;
  float sync_x;
  float sync_y;
  float sync_angle;
};

// MCU/车身 → gateway 的粗总线源（画布 external 节点）
struct VehicleBus {
  uint64_t timestamp_ns;
  uint8_t _opaque[1];
};

// 规划回传 → gateway 下发控车（CAN / IPC）
struct Trajectory {
  uint64_t timestamp_ns;
  uint8_t point_count;
  float points_x_m[60];
  float points_y_m[60];
  uint8_t gear_shift_first;
  uint8_t gear_shift_second;
};

}  // namespace gf::demo::vehicle_gateway
