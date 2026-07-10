// SOA Platform sheet (app.xlsx) → MCU↔AP IPC + gateway 边界类型
// synthesize: gf-codegen synthesize module --from-hpp io_types.hpp --meta module.meta.yaml

#pragma once

#include <cstdint>

namespace gf::demo::mcu_cp_gateway {

// --- MCU → AP（与 AUTOSAR CP IPC 对齐，P0 主路径 5 类）---

struct IPC_CanInfo_20ms_St {
  float fVehicleSpeed;
  float fYawRate;
  float fLeftFrontWheelSpeed;
  float fRightFrontWheelSpeed;
  float fLeftRearWheelSpeed;
  float fRightRearWheelSpeed;
};

struct IPC_CanInfo_10ms_St {
  float fSteerAngle;
  uint8_t ucGear;
  float uiSyncX;
  float uiSyncY;
  float uiSyncAngle;
  float fParkingSlot_P0X;
  float fParkingSlot_P0Y;
};

struct IPC_CanInfo_100ms_St {
  uint8_t uiAPAOnOff;
  uint8_t uiAPAMode;
  uint8_t uiAPAStatus;
  uint8_t uiAVMOnOff;
  uint8_t uiAVMMode;
};

// --- AP → MCU ---

struct IPC_TrajPlot_St {
  uint8_t PointLength;
  float PointX[60];
  float PointY[60];
  uint8_t GearShiftPointFst;
  uint8_t GearShiftPointScd;
};

struct IPC_P_Parking_St {
  double PACtl_StrCtl_angCmdEPS_avm;
  double PACtl_LngCtl_lVehDisDes_avm;
  double PACtl_ProMng_numGearDes_avm;
  double PACtl_LngCtl_stEbrkExt_avm;
};

// --- Gateway 对外 semantic 类型（gf_ara::com Event payload）---

struct EgoMotion {
  uint64_t timestamp_ns;
  float speed_mps;
  float yaw_rate_degps;
  float steer_angle_deg;
  uint8_t gear;
  float wheel_speed_fl_mps;
  float wheel_speed_fr_mps;
  float wheel_speed_rl_mps;
  float wheel_speed_rr_mps;
};

struct ParkingSlot {
  uint8_t slot_id;
  float p0_x_m;
  float p0_y_m;
  float p1_x_m;
  float p1_y_m;
  float p2_x_m;
  float p2_y_m;
};

struct EgoMotionExtended {
  uint64_t timestamp_ns;
  float steer_angle_deg;
  uint8_t gear;
  float sync_x_m;
  float sync_y_m;
  float sync_angle_deg;
  ParkingSlot selected_slot;
};

struct VehicleModeStatus {
  uint8_t apa_on_off;
  uint8_t apa_mode;
  uint8_t apa_status;
  uint8_t avm_on_off;
  uint8_t avm_mode;
};

struct Trajectory {
  uint8_t point_count;
  float points_x_m[60];
  float points_y_m[60];
  uint8_t gear_shift_first;
  uint8_t gear_shift_second;
};

struct ActuatorCommand {
  double steer_cmd_deg;
  double long_distance_des_m;
  double gear_des;
  double ebrake_ext;
};

}  // namespace gf::demo::mcu_cp_gateway
