#pragma once

#include <cstdint>
#include <optional>
#include <string>

#include "gf_ara/com/binding/iceoryx/event.hpp"
#include "gf_ara/com/service_path.hpp"
#include "iceoryx_posh/popo/subscriber.hpp"

namespace gf_gen {

struct Perception_APP_Out_St {
  uint32_t APP_Datalength;
  uint32_t APP_CRC;
  uint32_t APP_Frame_ID;
  uint64_t APP_Timestamp;
  uint8_t APP_Main_State;
  uint8_t APP_Cam_State;
  float APP_Cam_Temperature;
  float APP_Sensor_Framerate;
  float APP_Perception_Framerate;
  float APP_Latency;
};

struct Dyn_OBJ_Item_St {
  uint8_t m_OBJ_ID;
  uint8_t m_OBJ_Object_Class;
  uint8_t m_OBJ_IsCutin;
  float m_OBJ_Width;
  float m_OBJ_Length;
  float m_OBJ_Height;
  float m_OBJ_Abs_Long_Velocity;
  float m_OBJ_Abs_Long_Velocity_STD;
  float m_OBJ_Abs_Lat_Velocity;
  float m_OBJ_Abs_Lat_Velocity_STD;
  float m_OBJ_Relative_Long_Velocity;
  float m_OBJ_Relative_Lat_Velocity;
  uint8_t m_OBJ_Lane_Assignment;
  float m_OBJ_Abs_Long_Acc;
  float m_OBJ_Abs_Long_Acc_STD;
  float m_OBJ_Abs_Lat_Acc;
  float m_OBJ_Abs_Lat_Acc_STD;
  float m_OBJ_Relative_Long_Acc;
  float m_OBJ_Relative_Long_Acc_STD;
  float m_OBJ_Long_Distance;
  float m_OBJ_Long_Distance_STD;
  float m_OBJ_Lat_Distance;
  float m_OBJ_Lat_Distance_STD;
  float m_OBJ_Abs_Acceleration;
  float m_OBJ_Heading;
  float m_OBJ_Existence_Probability;
  uint8_t m_OBJ_Motion_Category;
  uint32_t m_OBJ_Object_Age;
  uint8_t m_OBJ_Measuring_Status;
  float m_OBJ_Class_Probability;
  uint8_t m_OBJ_Motion_Status;
  bool m_OBJ_Right_Out_Of_Image;
  bool m_OBJ_Left_Out_Of_Image;
  bool m_OBJ_Top_Out_Of_Image;
  bool m_OBJ_Bottom_Out_Of_Image;
  float m_OBJ_Absolute_Speed;
  float m_OBJ_Angle_Rate;
  float m_OBJ_Angle_Right;
  float m_OBJ_Angle_Left;
  float m_OBJ_Angle_Side;
  float m_OBJ_Angle_Mid;
};

struct Perception_Dyn_OBJ_Out_St {
  uint32_t OBJ_Datalength;
  uint32_t OBJ_CRC;
  uint32_t m_frame_id;
  uint64_t m_time_stamp;
  uint8_t m_OBJ_Ped_Count;
  uint8_t m_OBJ_VD_Count;
  uint8_t m_OBJ_VD_Allow_Acc;
  uint8_t m_OBJ_VD_CIPV_ID;
  uint8_t m_OBJ_VD_CIPV_Lost;
  uint8_t m_OBJ_VD_NIV_Left;
  uint8_t m_OBJ_VD_NIV_Right;
  uint8_t m_OBJ_VD_Pre_Cutin_ID;
  uint8_t m_OBJ_VD_OCC_ID;
  Dyn_OBJ_Item_St m_Obj_item[13];
};

struct Static_OBJ_Item_St {
  uint8_t m_OBJ_ID;
  uint8_t m_OBJ_Object_Class;
  float m_OBJ_Width;
  float m_OBJ_Length;
  uint8_t m_OBJ_Lane_Assignment;
  float m_OBJ_Long_Distance;
  float m_OBJ_Lat_Distance;
  float m_OBJ_Heading;
  float m_OBJ_Existence_Probability;
  uint32_t m_OBJ_Object_Age;
  float m_OBJ_Class_Probability;
  float m_OBJ_Angle_Right;
  float m_OBJ_Angle_Left;
  float m_OBJ_Angle_Side;
  float m_OBJ_Angle_Mid;
};

struct Perception_Static_Obj_Out_St {
  uint32_t STAT_OBJ_Datalength;
  uint32_t STAT_OBJ_CRC;
  uint32_t m_frame_id;
  uint64_t m_time_stamp;
  uint8_t m_Static_OBJ_Count;
  uint8_t STAT_OBJ_Static_CIPV_ID;
  Static_OBJ_Item_St m_Obj_item[10];
};

struct FCF_VD_St {
  uint8_t m_FCF_VD_Dyn_SET_ID;
  uint8_t m_FCF_VD_Dyn_Alert;
  uint8_t m_FCF_VD_Obj_ID;
  float m_FCF_VD_TTC;
  float m_FCF_VD_TTC_Thres;
  float FCF_rel_demand_deceleration;
  float FCF_target_deceleration;
  uint8_t m_FCF_VD_AEB_SuppressReason;
  uint8_t m_FCF_VD_FCW_SuppressReason;
};

struct FCF_VRU_St {
  uint8_t m_FCF_VRU_Dyn_Level_ID;
  uint8_t m_FCF_VRU_Dyn_Alert;
  uint8_t m_FCF_VRU_Obj_ID;
  float m_FCF_VRU_TTC;
  float m_FCF_VRU_TTC_Thres;
  float FCF_rel_demand_deceleration;
  float FCF_target_deceleration;
  uint8_t m_FCF_VRU_AEB_SuppressReason;
  uint8_t m_FCF_VRU_FCW_SuppressReason;
};

struct FCF_CV_St {
  uint8_t m_FCF_CV_Dyn_Alert_Level;
  uint8_t m_FCF_CV_Dyn_Alert;
  uint8_t m_FCF_CV_Obj_ID;
  float m_FCF_CV_TTC;
  float m_FCF_CV_TTC_Thres;
  float FCF_rel_demand_deceleration;
  float FCF_target_deceleration;
  uint8_t m_FCF_CV_AEB_SuppressReason;
  uint8_t m_FCF_CV_FCW_SuppressReason;
};

struct Perception_FCF_Out_St {
  uint32_t FCF_Datalength;
  uint32_t FCF_CRC;
  uint32_t m_frame_id;
  uint64_t m_time_stamp;
  bool asil_fcw_vo_seta;
  bool asil_aeb_vo_sete;
  uint8_t aeb_resource;
  FCF_VD_St m_FCF_VD_Info[8];
  FCF_VRU_St m_FCF_VRU_Info[8];
  FCF_CV_St m_FCF_CV_Info[8];
};

struct HostLine_St {
  uint8_t LH_Track_ID;
  uint8_t m_LH_Side;
  float m_LH_Confidence;
  uint8_t m_LH_Availability_State;
  uint8_t m_LH_Lanemark_Type;
  float m_LH_First_VR_Start;
  float m_LH_First_VR_End;
  float m_LH_Marker_Width;
  float m_LH_Line_First_C0;
  float m_LH_Line_First_C1;
  float m_LH_Line_First_C2;
  float m_LH_Line_First_C3;
  uint8_t m_LH_Color;
  uint8_t m_LH_DLM_Type;
  uint8_t m_LH_DECEL_Type;
  bool m_LH_Crossing;
};

struct Perception_LH_Out_St {
  uint32_t LH_Datalength;
  uint32_t LH_CRC;
  uint32_t m_frame_id;
  uint64_t m_time_stamp;
  uint8_t m_hostline_num;
  float m_LH_Estimated_Width;
  HostLine_St m_hostline[2];
};

struct Perception_HLB_Out_St {
  uint32_t HLB_Datalength;
  uint32_t HLB_CRC;
  uint32_t m_frame_id;
  uint64_t m_time_stamp;
  uint8_t m_HLB_Decision;
  uint32_t m_HLB_Reason;
};

struct Perception_FS_Out_St {
  uint32_t FS_Datalength;
  uint32_t FS_CRC;
  uint32_t m_frame_id;
  uint64_t m_time_stamp;
  bool m_FS_Free_Sight;
  uint8_t m_FS_Full_Blockage;
  uint8_t m_FS_Rain;
  uint8_t m_FS_Fog;
  uint8_t m_FS_Splashes;
  uint8_t m_FS_Sun_Ray;
  uint8_t m_FS_Low_Sun;
  uint8_t m_FS_Blur_Image;
  uint8_t m_FS_Partial_Blockage;
  uint8_t m_FS_Frozen_Windshield_Lens;
  uint8_t m_FS_Out_Of_Focus;
};

struct TSR_Item_St {
  uint8_t m_DSTSR_ID;
  uint8_t m_DSTSR_Sign_Name;
  float m_DSTSR_Sign_Long_Distance;
  float m_DSTSR_Sign_Lat_Distance;
  float m_DSTSR_Sign_Height;
  uint8_t m_DSTSR_Sign_Shape;
  uint8_t m_DSTSR_Relevancy;
  float m_DSTSR_Sup1_Confidence;
  float m_DSTSR_Confidence;
  float m_DSTSR_Relevancy_Confidence;
  uint32_t m_DSTSR_Tracking_Out_of_Image;
  uint8_t m_DSTSR_Sup1_SignName;
};

struct Perception_DSTSR_Out_St {
  uint32_t DSTSR_Datalength;
  uint32_t DSTSR_CRC;
  uint32_t m_frame_id;
  uint64_t m_time_stamp;
  uint8_t m_tsr_num;
  TSR_Item_St m_TSR_Item[6];
};

struct LA_Line_St {
  uint8_t LA_Track_ID;
  float m_LA_Confidence;
  uint8_t m_LA_Availability_State;
  float m_LA_View_Range_Start;
  float m_LA_View_Range_End;
  uint8_t m_LA_Lanemark_Type;
  uint8_t m_LA_Line_Side;
  float m_LA_Line_C3;
  float m_LA_Line_C2;
  float m_LA_Line_C1;
  float m_LA_Line_C0;
};

struct Perception_LA_Out_St {
  uint32_t LA_Datalength;
  uint32_t LA_CRC;
  uint32_t m_frame_id;
  uint64_t m_time_stamp;
  uint8_t m_adj_line_num;
  LA_Line_St m_adj_line[4];
};

struct LRE_Line_St {
  uint8_t LRE_Track_ID;
  float m_LRE_Confidence;
  uint8_t m_LRE_Availability_State;
  float m_LRE_View_Range_Start;
  float m_LRE_View_Range_End;
  float m_LRE_Line_C3;
  float m_LRE_Line_C2;
  float m_LRE_Line_C1;
  float m_LRE_Line_C0;
  uint8_t m_LRE_Side;
};

struct Perception_LRE_Out_St {
  uint32_t LRE_Datalength;
  uint32_t LRE_CRC;
  uint32_t m_frame_id;
  uint64_t m_time_stamp;
  uint8_t m_roadedge_num;
  LRE_Line_St m_roadedge_line[2];
};

struct AF_CamCalibResult_St {
  float cam_tx;
  float cam_ty;
  float cam_tz;
  float cam_pitch;
  float cam_yaw;
  float cam_roll;
};

struct Perception_AF_Out_St {
  uint32_t AF_Datalength;
  uint32_t AF_CRC;
  uint32_t AF_Frame_ID;
  uint64_t AF_Timestamp;
  uint8_t AF_calib_status;
  uint8_t AF_calib_progress;
  AF_CamCalibResult_St AF_calib_result;
};

struct Perception_MESSAGE_Out_St {
  Perception_APP_Out_St Perception_APP_Out;
  Perception_Dyn_OBJ_Out_St Perception_DYN_OBJ_Out;
  Perception_Static_Obj_Out_St Perception_STATIC_OBJ_Out;
  Perception_FCF_Out_St Perception_FCF_Out;
  Perception_LH_Out_St Perception_LH_Out;
  Perception_HLB_Out_St Perception_HLB_Out;
  Perception_FS_Out_St Perception_FS_Out;
  Perception_DSTSR_Out_St Perception_DSTSR_Out;
  Perception_LA_Out_St Perception_LA_Out;
  Perception_LRE_Out_St Perception_LRE_Out;
  Perception_AF_Out_St Perception_AF_Out;
};

class Perception_MESSAGE_Out_StSkeleton {
 public:
  static constexpr const char* kService = "semantic.Perception_MESSAGE_Out_St";
  static constexpr const char* kEvent = "Perception_MESSAGE_Out_St";

  explicit Perception_MESSAGE_Out_StSkeleton(std::string instance = "1")
      : pub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}

  gf_ara::core::Result<void> Send(const Perception_MESSAGE_Out_St& sample) {
    return pub_.Publish(sample);
  }

 private:
  gf_ara::com::binding::iceoryx::EventPublisher<Perception_MESSAGE_Out_St> pub_;
};

class Perception_MESSAGE_Out_StProxy {
 public:
  static constexpr const char* kService = "semantic.Perception_MESSAGE_Out_St";
  static constexpr const char* kEvent = "Perception_MESSAGE_Out_St";

  explicit Perception_MESSAGE_Out_StProxy(std::string instance = "1")
      : sub_{gf_ara::com::ServicePath{kService, std::move(instance), kEvent}} {}

  gf_ara::core::Result<std::optional<Perception_MESSAGE_Out_St>> Take() {
    return sub_.Take();
  }

  [[nodiscard]] bool HasData() const noexcept { return sub_.HasData(); }

  [[nodiscard]] iox::popo::Subscriber<Perception_MESSAGE_Out_St>& Native() noexcept {
    return sub_.Native();
  }
  [[nodiscard]] const iox::popo::Subscriber<Perception_MESSAGE_Out_St>& Native() const noexcept {
    return sub_.Native();
  }

 private:
  gf_ara::com::binding::iceoryx::EventSubscriber<Perception_MESSAGE_Out_St> sub_;
};

}  // namespace gf_gen
