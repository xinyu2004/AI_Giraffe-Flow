#ifndef PERCEPTION_OUT_MESSAGES_H_
#define PERCEPTION_OUT_MESSAGES_H_

/*****************Perception Out Protocol V0.9  20260206************************************
Change List:
	V0.1
		1. Initial Version
	V0.2
		1. Add enum definition of TSR Name and TSR SUPP Name.
		2. Add m_time_stamp for each pack.
		3. Add 4 bytes alignment.
                V0.3
 		1. Add frame id for each pack.
                V0.4
                                1. Add some signals for FCF.
                V0.5    
                                1. Add cone/barrier/barrel/tripod type for OBJ_Object_Class
                                2. Change m_DSTSR_Sign_Name and m_DSTSR_Sup1_SignName to enum type
                                3. Combine TTC Thres signal
                                4. Change m_HLB_Reason from enum to uint32_t
                                5. Add enum definition for AEB/FCW SuppressReason
                                6. Add unknown for TSR type and suppl type.
                V0.6
                                1. Split dynamic and static objects.
                                2. Combine single message
                                3. Change ID range from 1~255 to 1~127
	v0.7
		1. Add m_OBJ_VD_Pre_Cutin_ID and m_OBJ_VD_OCC_ID for dynamic object
		2. Split FCF signal array
		3. Move m_LH_Crossing signal position
                v0.8
                                1. Remove bitwise definition for AEB/FCW SUPPRESS REASON
                                2. Add some signals for FCF.
                v0.9
                                1. Add deceleration value for FCF message. 
	V1.0
	1. 增加报文PERCEPTION_MESSAGE_APP_OUT，用于传输感知算法通用信息
    2. 增加报文PERCEPTION_MESSAGE_AF_OUT，用于传输Autyofix信息
	3. 统一增加数据长度和CRC进行数据保护
	4. PERCEPTION_MESSAGE_APP_OUT增加帧率/延迟等信息
	5. PERCEPTION_MESSAGE_DYN_OBJ_OUT增加VRU/VD数量等信息
	6. 车道线/路沿统一增加Track ID
	
	V1.1
	1. 变更OBJ_VD_CIPV_Lost枚举类型
	2. 变更OBJ_Object_Class枚举类型
	
	V1.2
	1. 勘误，APP_Main_State_em/APP_Cam_State_em/APP_Init_Error_em/APP_Diag_Error_em枚举值增加前缀以避免重复
	2. 修改DYN_OBJ_MAX_NUM=13/STATIC_OBJ_MAX_NUM=10/TSR_OBJ_MAX_NUM=6
	
	V1.3
	1. 勘误，AF_AutoCamCalibStatus_em枚举值增加AF_前缀以避免重复
	
	V1.4
	1. 动态目标增加相对加速度，标准差等信息
	2. 动态目标增加是否cutin信息
	3. 所有感知数据报文整合为一整个大结构体
	
	V1.5
	1. 修改APP_Init_Error_em/APP_Diag_Error_em定义，增加故障内容
	
	V1.6
	1. 修改FCF_VRU_Dyn_Level_ID，定义FCF_VRU_DYN_L2为partial brake
*************************************************************************************************/

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

#include <stdbool.h>

#pragma pack(push,4)   //4字节对齐


#define FCF_MAX_NUM             8
#define DYN_OBJ_MAX_NUM         13
#define STATIC_OBJ_MAX_NUM   	10
#define HOST_LINE_MAX_NUM    	2
#define ROAD_EDGE_MAX_NUM    	2
#define ADJ_LINE_MAX_NUM      	4
#define TSR_OBJ_MAX_NUM       	6

enum OBJ_VD_Allow_Acc 
{
    OBJ_VD_ALLOW_FREE_SPACE=0,		//前方为可行驶区域
    OBJ_VD_ALLOW_SPACE_NOT_FREE=1,	//前方非可行驶区域
    OBJ_VD_ALLOW_FREE_SPACE_UNKNOWN=2	//前方未知
} ;

enum OBJ_VD_CIPV_Lost 
{
    NO_LOSS=0,                           //默认值
    NO_CIPV_CHANGE=1,                   // CIPV没有变动
    CURRENT_TARGET_CUTOUT=2,            //目标切出导致不再选取
    CURRENT_TARGET_TRACK_LOSS=3,        //目标本身丢失跟踪导致不再选取
    ANOTHER_URGENT_CIPV_SELECTED=4,     //有其他更紧急的目标抢占cipv
    OTHER_REASON=5                      //其他原因导致目标停止选取
} ;

enum OBJ_Object_Class 
{
    OBJ_OBJECT_CLASS_UNFILLED=0x00,	//未定义类型
    OBJ_OBJECT_CLASS_CAR=0x01,	//轿车、SUV
    OBJ_OBJECT_CLASS_TRUCK=0x02,	//卡车、大巴车
    OBJ_OBJECT_CLASS_MOTORBIKE=0x03,	//摩托车(机动车类)
    OBJ_OBJECT_CLASS_BICYCLE=0x04,	//自行车
    OBJ_OBJECT_CLASS_PEDESTRIAN=0x05,	//行人
    OBJ_OBJECT_CLASS_GENERAL_OBJECT=0x06,	//一般障碍物
    OBJ_OBJECT_CLASS_ANIMAL=0x07,		//动物，暂未使用
    OBJ_OBJECT_CLASS_UNCERTAIN_VCL=0x08,	//暂未使用
    OBJ_OBJECT_CLASS_TWO_WHEELER=0x09,	//两轮车(电瓶/电动两轮车)
	OBJ_OBJECT_CLASS_THREE_WHEELER=0x0A,//三轮车
    OBJ_OBJECT_CLASS_CONE=0x81,                   //锥桶
    OBJ_OBJECT_CLASS_BARRIER=0x82,             //水马
    OBJ_OBJECT_CLASS_BARREL=0x83,              //防撞桶/圆桶
    OBJ_OBJECT_CLASS_TRIPOD=0x84                     //警示三角架
} ;

enum OBJ_Lane_Assignment 
{
    OBJ_LANE_UNKNOWN=0,   //未知车道
    OBJ_LANE_LEFT_LEFT=1,	//左左车道
    OBJ_LANE_LEFT=2,	//左车道
    OBJ_LANE_HOST=3,	//当前车道
    OBJ_LANE_RIGHT=4,	//右车道
    OBJ_LANE_RIGHT_RIGHT=5	//右右车道
} ;

enum OBJ_Motion_Category   //目标运动类别，参考图示定义
{
    OBJ_MOTION_CATEGORY_UNFILLED=0,
    OBJ_MOTION_CATEGORY_UNDEFINED=1,
    OBJ_MOTION_CATEGORY_PASSING=2,
    OBJ_MOTION_CATEGORY_PASSING_IN=3,
    OBJ_MOTION_CATEGORY_PASSING_OUT=4,
    OBJ_MOTION_CATEGORY_CLOSE_CUT_IN=5,
    OBJ_MOTION_CATEGORY_MOVING_IN=6,
    OBJ_MOTION_CATEGORY_MOVING_OUT=7,
    OBJ_MOTION_CATEGORY_CROSSING=8,
    OBJ_MOTION_CATEGORY_LTAP=9,
    OBJ_MOTION_CATEGORY_RTAP=10,
    OBJ_MOTION_CATEGORY_MOVING=11,
    OBJ_MOTION_CATEGORY_PRECEEDING=12,
    OBJ_MOTION_CATEGORY_ONCOMING=13
} ;

enum OBJ_Measuring_Status //目标测量状态
{
    OBJ_MEASURING_OLD_OR_NEW=(1<<0), //(BIT_0)   是否新目标？
    OBJ_MEASURING_PREDICTED_OR_MEASURED=(1<<1), //(BIT_1)   测量或预测？
    OBJ_MEASURING_NOT_VALID_OR_VALID=(1<<2) //(BIT_2)   有效或无效?
} ;

enum OBJ_Motion_Status   //目标运动状态
{
    OBJ_MOTION_INVALID=0,
    OBJ_MOTION_UNKNOWN=1,		//目标运动状态未知
    OBJ_MOTION_MOVING=2, 		//目标运动中
    OBJ_MOTION_STATIONARY=3, 		//目标静止中
    OBJ_MOTION_STOPPED=4, 		//目标从运动变为静止
    OBJ_MOTION_MOVING_SLOWLY=5 		//目标慢速运动
} ;

enum OBJ_IsCutin_em   //目标运动状态
{
    OBJ_ISCUTIN_FALSE=0,  //未识别到cutin趋势
    OBJ_ISCUTIN_TRUE=1 	  //识别到cutin趋势
} ;

typedef struct
{
    uint8_t m_OBJ_ID;			//目标ID， 1~127     0:无效目标
    OBJ_Object_Class m_OBJ_Object_Class;	//目标类别，轿车/卡车/行人/两轮车/...
	OBJ_IsCutin_em m_OBJ_IsCutin;   //目标是否有cutin趋势
    float m_OBJ_Width;			//目标宽度，单位m
    float m_OBJ_Length;			//目标长度，单位m
	float m_OBJ_Height;          //目标高度，单位m
    float m_OBJ_Abs_Long_Velocity;		//目标纵向绝对速度，单位m/s
	float m_OBJ_Abs_Long_Velocity_STD;            //目标纵向绝对速度标准差，单位m/s
    float m_OBJ_Abs_Lat_Velocity;		//目标横向绝对速度，单位m/s
	float m_OBJ_Abs_Lat_Velocity_STD;               //目标横向绝对速度标准差，单位m/s
    float m_OBJ_Relative_Long_Velocity;		//目标相对纵向速度，单位m/s
    float m_OBJ_Relative_Lat_Velocity;		//目标相对横向速度，单位m/s
    OBJ_Lane_Assignment m_OBJ_Lane_Assignment;	//目标所在车道
    float m_OBJ_Abs_Long_Acc;		     //目标绝对纵向加速度，单位m/s2
	float m_OBJ_Abs_Long_Acc_STD;         //目标绝对纵向加速度标准差，单位m/s2
    float m_OBJ_Abs_Lat_Acc;			 //目标横向绝对加速度，单位m/s2
	float m_OBJ_Abs_Lat_Acc_STD;          //目标横向绝对加速度标准差，单位m/s2
	float m_OBJ_Relative_Long_Acc;        //目标相对纵向加速度，单位m/s2
	float m_OBJ_Relative_Long_Acc_STD;    //目标相对纵向加速度标准差，单位m/s2
    float m_OBJ_Long_Distance;		     //目标纵向距离，单位m
	float m_OBJ_Long_Distance_STD;        //纵向距离标准差，单位m
    float m_OBJ_Lat_Distance;			//目标横向距离，单位m
	float m_OBJ_Lat_Distance_STD;                        //横向距离标准差，单位m
    float m_OBJ_Abs_Acceleration;		//目标绝对加速度，单位m/s2
    float m_OBJ_Heading;			//目标航向角，单位rad
    float m_OBJ_Existence_Probability;		//目标存在可信度
    OBJ_Motion_Category m_OBJ_Motion_Category;	//目标运动类别    CUT-IN/PASS-IN/PASS-OUT/...
    uint32_t m_OBJ_Object_Age;			//目标存在帧数
    OBJ_Measuring_Status m_OBJ_Measuring_Status;	//目标测量状态
    float m_OBJ_Class_Probability;			//目标类别可信度
    OBJ_Motion_Status m_OBJ_Motion_Status;		//目标运动状态    移动/静止/停止/慢速移动/...
    bool m_OBJ_Right_Out_Of_Image;			//目标超出图像右边界
    bool m_OBJ_Left_Out_Of_Image;			//目标超出图像左边界
    bool m_OBJ_Top_Out_Of_Image;			//目标超出图像上边界
    bool m_OBJ_Bottom_Out_Of_Image;			//目标超出图像下边界
    float m_OBJ_Absolute_Speed;			//目标绝对速度  m/s
    float m_OBJ_Angle_Rate;				//目标瞬时角速度  rad/s
    float m_OBJ_Angle_Right;				//目标右侧近端与本车中轴的夹角  rad
    float m_OBJ_Angle_Left;				//目标左侧近端与本车中轴的夹角  rad
    float m_OBJ_Angle_Side;				//目标可见远端与本车中轴的夹角  rad
    float m_OBJ_Angle_Mid;                                                     //目标近端中部与本车中轴的夹角  rad
}Dyn_OBJ_Item_St;

typedef struct
{
	uint32_t  OBJ_Datalength;     //Data length of PERCEPTION_DYN_OBJ_OUT
	uint32_t  OBJ_CRC;            //CRC32-IEEE 802.3
    uint32_t  m_frame_id;			//图像帧号
    uint64_t  m_time_stamp;                                      //时间戳  单位us
    uint8_t m_OBJ_Ped_Count;			//输出的VRU目标数量
	uint8_t m_OBJ_VD_Count;			//输出的车辆目标数量
    OBJ_VD_Allow_Acc m_OBJ_VD_Allow_Acc;	//ACC允许条件，前方是否可行驶区域
    uint8_t m_OBJ_VD_CIPV_ID;			//CIPV目标ID
    OBJ_VD_CIPV_Lost m_OBJ_VD_CIPV_Lost;	//CIPV消失原因
    uint8_t m_OBJ_VD_NIV_Left;		//左侧NIV目标ID
    uint8_t m_OBJ_VD_NIV_Right;		//右侧NIV目标ID
    uint8_t m_OBJ_VD_Pre_Cutin_ID;  		//即将切入目标ID
    uint8_t m_OBJ_VD_OCC_ID;        		//备选CIPV目标ID

    Dyn_OBJ_Item_St  m_Obj_item[DYN_OBJ_MAX_NUM];       //动态障碍物详细信息
} Perception_Dyn_OBJ_Out_St;

typedef struct
{
    uint8_t m_OBJ_ID;			//目标ID， 1~127     0:无效目标
    OBJ_Object_Class m_OBJ_Object_Class;	//目标类别，轿车/卡车/行人/两轮车/...
    float m_OBJ_Width;			//目标宽度，单位m
    float m_OBJ_Length;			//目标长度，单位m
    OBJ_Lane_Assignment m_OBJ_Lane_Assignment;	//目标所在车道
    float m_OBJ_Long_Distance;		//目标纵向距离，单位m
    float m_OBJ_Lat_Distance;			//目标横向距离，单位m
    float m_OBJ_Heading;			//目标航向角，单位rad
    float m_OBJ_Existence_Probability;		//目标存在可信度
    uint32_t m_OBJ_Object_Age;		//目标存在帧数
    float m_OBJ_Class_Probability;		//目标类别可信度
    float m_OBJ_Angle_Right;			//目标右侧近端与本车中轴的夹角  rad
    float m_OBJ_Angle_Left;			//目标左侧近端与本车中轴的夹角  rad
    float m_OBJ_Angle_Side;			//目标可见远端与本车中轴的夹角  rad
    float m_OBJ_Angle_Mid;                                      //目标近端中部与本车中轴的夹角  rad
}Static_OBJ_Item_St;

typedef struct
{
	uint32_t  STAT_OBJ_Datalength;     //Data length of PERCEPTION_STAT_OBJ_OUT
	uint32_t  STAT_OBJ_CRC;            //CRC32-IEEE 802.3
    uint32_t  m_frame_id;			//图像帧号
    uint64_t  m_time_stamp;                                      //时间戳  单位us
    uint8_t m_Static_OBJ_Count;		//静态目标个数
    uint8_t STAT_OBJ_Static_CIPV_ID;		//静态目标CIPV
	
    Static_OBJ_Item_St  m_Obj_item[STATIC_OBJ_MAX_NUM];                     //静态障碍物详细信息
}Perception_Static_Obj_Out_St;

enum FCF_VD_Dyn_SET_ID 
{
    A=0,		//FCW
    B=1,		//Partial Brake
    C=2,		//Full Brake
    D=3,		//EBA
    E=4,		//TBD
    F=5,		//TBD
    G=6,		//TBD
    H=7		//TBD
} ;

enum FCF_VD_Dyn_Alert 
{
    FCF_VD_DYN_NO_ALERT=0x9966,
    FCF_VD_DYN_ALERT=0xAA55
} ;

enum FCF_VRU_Dyn_Alert 
{
    FCF_VRU_DYN_NO_ALERT=0x9966,
    FCF_VRU_DYN_ALERT=0xAA55
} ;

enum FCF_VRU_Dyn_Level_ID 
{
    FCF_VRU_DYN_L1=0,	//Full Brake
    FCF_VRU_DYN_L2=1,	//Partial Brake
    FCF_VRU_DYN_L3=2,	//FCW
    FCF_VRU_DYN_L4=3,	//Prefill
    FCF_VRU_DYN_L5=4,	//EBA
    FCF_VRU_DYN_L6=5,	//AWB
    FCF_VRU_DYN_L7=6,
    FCF_VRU_DYN_L8=7,
} ;

enum FCF_VD_Dyn_HeadWay_Alert 
{
    FCF_VD_DYN_HEADWAY_NO_ALERT=0,
    FCF_VD_DYN_HEADWAY_ALERT=1
} ;

enum FCF_CV_Dyn_Alert_Level 
{
    FCF_CV_DYN_ALERT_L1=0,		//Full Brake
    FCF_CV_DYN_ALERT_L2=1,		//Soft Brake
    FCF_CV_DYN_ALERT_L3=2,		//FCW
    FCF_CV_DYN_ALERT_L4=3,		//AWB
    FCF_CV_DYN_ALERT_L5=4,		//prefill
    FCF_CV_DYN_ALERT_L6=5,
    FCF_CV_DYN_ALERT_L7=6,
    FCF_CV_DYN_ALERT_L8=7
} ;

enum FCF_CV_Dyn_Alert 
{
    FCF_CV_DYN_ALERT_NO_ALERT=39270,
    FCF_CV_DYN_ALERT_ALERT=43605
} ;

typedef struct
{
    FCF_VD_Dyn_SET_ID m_FCF_VD_Dyn_SET_ID;			//FCF VD报警ID  A-H(0-7)
    FCF_VD_Dyn_Alert m_FCF_VD_Dyn_Alert;			//FCF VD报警Flag
    uint8_t  m_FCF_VD_Obj_ID;                                                                 //FCF  VD报警目标ID (1~255)
    float m_FCF_VD_TTC;                                                                     	//FCF  VD报警目标TTC值(0.00~10.00s)
    float m_FCF_VD_TTC_Thres;                                                  	//FCF  VD报警对应的TTC阈值(0.00~10.00s)
    float FCF_rel_demand_deceleration;				//FCF 需求减速度值(0 ~ -10m/s^2)
    float FCF_target_deceleration;                                                           //FCF 请求下发的减速度值(0 ~ -10m/s^2)
    uint8_t m_FCF_VD_AEB_SuppressReason;                                        //FCF  VD报警AEB抑制原因
    uint8_t m_FCF_VD_FCW_SuppressReason;                                       //FCF  VD报警FCW抑制原因
}FCF_VD_St;

typedef struct
{
    FCF_VRU_Dyn_Level_ID m_FCF_VRU_Dyn_Level_ID;		//FCF VRU报警ID Level1-8(0-7)
    FCF_VRU_Dyn_Alert m_FCF_VRU_Dyn_Alert;			//FCF VRU报警Flag
    uint8_t  m_FCF_VRU_Obj_ID;                                                                 //FCF  VRU报警目标ID (1~255)
    float m_FCF_VRU_TTC;                                                                     	//FCF  VRU报警目标TTC值(0.00~10.00s)
    float m_FCF_VRU_TTC_Thres;                                                  	//FCF  VRU报警对应的TTC阈值(0.00~10.00s)
    float FCF_rel_demand_deceleration;				//FCF 需求减速度值(0 ~ -10m/s^2)
    float FCF_target_deceleration;                                                           //FCF 请求下发的减速度值(0 ~ -10m/s^2)
    uint8_t m_FCF_VRU_AEB_SuppressReason;                                        //FCF  VRU报警AEB抑制原因
    uint8_t m_FCF_VRU_FCW_SuppressReason;                                       //FCF  VRU报警FCW抑制原因
}FCF_VRU_St;

typedef struct
{
    FCF_CV_Dyn_Alert_Level m_FCF_CV_Dyn_Alert_Level;	                //FCF 横穿车辆报警ID Level1-8(0-7)
    FCF_CV_Dyn_Alert m_FCF_CV_Dyn_Alert;			//FCF 横穿车辆报警Flag
    uint8_t  m_FCF_CV_Obj_ID;                                                                 //FCF  CV报警目标ID (1~255)
    float m_FCF_CV_TTC;                                                                          //FCF  CV报警目标TTC值(0.00~10.00s)
    float m_FCF_CV_TTC_Thres;                                                                //FCF  CV报警对应的TTC阈值(0.00~10.00s)
    float FCF_rel_demand_deceleration;			             //FCF 需求减速度值(0 ~ -10m/s^2)
    float FCF_target_deceleration;                                                           //FCF 请求下发的减速度值(0 ~ -10m/s^2)
    uint8_t m_FCF_CV_AEB_SuppressReason;                                        //FCF  CV报警AEB抑制原因
    uint8_t m_FCF_CV_FCW_SuppressReason;                                       //FCF  CV报警FCW抑制原因
}FCF_CV_St;

/*
场景 场景值：见《感知触发场景编码》sheet
cpla-20 1
cpla-40 2
cpla-60 3
cpla-80 4
cpla-20 5
cpla-40 6
cpla-60 7
cpla-80 8
cpfao-20 9
cpfao-40 10
cpfao-60 11
cpfao-20 12
cpfao-40 13
cpfao-60 14
cpnco-20 15
cpnco-40 16
cpnco-60 17
cpta-ln-10 18
cpta-ln-20 19
cpta-ln-30 20
cpta-lf-10 21
cpta-lf-20 22
cpta-lf-30 23
cpta-rf-10 24
cpta-rf-20 25
cbnao-20 26
cbnao-40 27
cbnao-60 28
csfao-20 29
csfao-40 30
csfao-60 31
cbla-20 32
cbla-40 33
cbla-60 34
cbla-80 35
csta-ln-10 36
csta-ln-20 37
csta-ln-30 38
csta-rn-10 39
csta-rn-20 40
ccrs-20 41
ccrs-30 42
ccrs-40 43
ccrs-50 44
ccrs-60 45
ccrs-70 46
ccrs-80 47
ccrh-80 48
ccrh-120 49
scp-30 50
scp-40 51
scp-50 52
scp-60 53
scpo-50 54
scpo-60 55
ccft-10 56
ccft-10 57
ccft-10 58
*/

typedef struct
{
	uint32_t  FCF_Datalength;     //Data length of PERCEPTION_STAT_OBJ_OUT
	uint32_t  FCF_CRC;            //CRC32-IEEE 802.3
    uint32_t  m_frame_id;				//图像帧号
    uint64_t  m_time_stamp;                                                     	//时间戳  单位us
    bool asil_fcw_vo_seta;          			//感知标准场景FCW触发
    bool asil_aeb_vo_sete;				//感知标准场景AEB触发
    uint8_t  aeb_resource;				//AEB触发的场景, 参考上面感知触发场景编码表
    FCF_VD_St m_FCF_VD_Info[FCF_MAX_NUM];                     //最大8个级别的预警类型
    FCF_VRU_St m_FCF_VRU_Info[FCF_MAX_NUM];                //最大8个级别的预警类型
    FCF_CV_St m_FCF_CV_Info[FCF_MAX_NUM];                     //最大8个级别的预警类型
} Perception_FCF_Out_St;

enum LH_Side 
{
    LH_SIDE_UNKNOWN=0,
    LH_SIDE_LEFT=1,		//本车道左线
    LH_SIDE_RIGHT=2	//本车道右线
} ;

enum LH_Availability_State 
{
    LH_NOT_AVAILABLE=0,
    LH_PREDICATED=1,	//预测结果
    LH_DETECTED=2		//检测结果
} ;

enum LH_Lanemark_Type 
{
    LH_LANEMARK_UNDECIDED=0,
    LH_LANEMARK_SOLID=1,		//实线
    LH_LANEMARK_DASHED=2,	//虚线
    LH_LANEMARK_DLM=3,		//双线
    LH_LANEMARK_BOTTS=4,		//点虚
    LH_LANEMARK_DECELERATION=5,	//减速线
    LH_LANEMARK_HOV_LANE=6	//HOV线
} ;

enum LH_Color 
{
    LH_COLOR_UNDECIDED=0,
    LH_COLOR_WHITE=1,		//白色
    LH_COLOR_YELLOW=2,		//黄色
    LH_COLOR_BLUE=3		//蓝色
} ;

enum LH_DLM_Type 
{
    LH_DLM_NOT_DLM=0,
    LH_DLM_SOLID_DASHED=1,	//实虚线
    LH_DLM_DASHED_SOLID=2,	//虚实线
    LH_DLM_SOLID_SOLID=3,		//双实线
    LH_DLM_DASHED_DASHED=4,	//双虚线
    LH_DLM_UNDECIDED=5
} ;

enum LH_DECEL_Type 
{
    LH_DECEL_NO_DECEL=0,
    LH_DECEL_SOLID=1,		//减速实线
    LH_DECEL_DASHED=2,		//减速虚线
    LH_DECEL_UNDECIDED=3,	
    LH_DECEL_RESERVED_2=4,
    LH_DECEL_RESERVED_3=5
} ;

typedef struct
{
	uint8_t LH_Track_ID;  //ID of the lane mark model
    LH_Side m_LH_Side;			//车道左线/右线
    float m_LH_Confidence;			//置信度
    LH_Availability_State m_LH_Availability_State;	//预测/检测
    LH_Lanemark_Type m_LH_Lanemark_Type;	//车道线类型
    float m_LH_First_VR_Start;			//车道线起始点
    float m_LH_First_VR_End;			//车道线结束点
    float m_LH_Marker_Width;			//车道线宽度,单位m
    float m_LH_Line_First_C0;			//三次多项式常数项
    float m_LH_Line_First_C1;			//三次多项式一次项系数
    float m_LH_Line_First_C2;			//三次多项式二次项系数
    float m_LH_Line_First_C3;			//三次多项式三次项系数
    LH_Color m_LH_Color;			//车道线颜色
    LH_DLM_Type m_LH_DLM_Type;		//双线类型
    LH_DECEL_Type m_LH_DECEL_Type;		//减速线类型
    bool m_LH_Crossing;			//跨线标志
}HostLine_St;

typedef struct
{
	uint32_t  LH_Datalength;     //Data length of PERCEPTION_LH_OUT
	uint32_t  LH_CRC;            //CRC32-IEEE 802.3
    uint32_t  m_frame_id;				//图像帧号
    uint64_t  m_time_stamp;                                                     	//时间戳  单位us
    uint8_t    m_hostline_num;                                                   //本车道线个数
    float m_LH_Estimated_Width;			//车道宽度，单位m

    HostLine_St  m_hostline[HOST_LINE_MAX_NUM];              //本车道线详细信息
} Perception_LH_Out_St;  //当前车道

enum HLB_Decision 
{
    HLB_DECISION_UNKNOWN=0,
    HLB_DECISION_HIGH=1,		//远光灯
    HLB_DECISION_LOW=2,		//近光灯
} ;

enum HLB_Reason  //每个reason占用1bit，可以多个reason同时存在
{
    HLB_REASON_TAIL_LIGHT=(1<<0), //(BIT_0)
    HLB_REASON_ONCOMING=(1<<1), //(BIT_1)
    HLB_REASON_ONCOMING_GRACE=(1<<2), //(BIT_2)
    HLB_REASON_TAIL_LIGHT_GRACE=(1<<3), //(BIT_3)
    HLB_REASON_LOW_SPEED=(1<<4), //(BIT_4)
    HLB_REASON_STREET_LIGHTS=(1<<5), //(BIT_5)
    HLB_REASON_SL_SCENE_GRACE=(1<<6), //(BIT_6)
    HLB_REASON_BRIGHT_SCENE=(1<<7), //(BIT_7)
    HLB_REASON_OBVIOUSLY_BRIGHT_SCENE=(1<<8), //(BIT_8)
    HLB_REASON_LIT_NIGHT=(1<<9), //(BIT_9)
    HLB_REASON_LIT_NIGHT_US=(1<<10), //(BIT_10)
    HLB_REASON_LIT_NIGHT_ECE=(1<<11), //(BIT_11)
    HLB_REASON_IN_VERY_SHARPE_CURVE=(1<<12), //(BIT_12)
    HLB_REASON_IN_CURVE=(1<<13), //(BIT_13)
    HLB_REASON_IN_BLINKING_TRAFFICLIGHT_SCENE=(1<<14), //(BIT_14)
    HLB_REASON_APPROACHING_JUNCTION=(1<<15), //(BIT_15)
    HLB_REASON_APPROACHING_ROUNDABOUT=(1<<16), //(BIT_16)
    HLB_REASON_IN_ROUNDABOUT=(1<<17), //(BIT_17)
    HLB_REASON_TUNNEL=(1<<18), //(BIT_18)
    HLB_REASON_RESERVED=(1<<19) //(BIT_19)
} ;

typedef struct
{
	uint32_t  HLB_Datalength;     //Data length of PERCEPTION_HLB_OUT
	uint32_t  HLB_CRC;            //CRC32-IEEE 802.3
    uint32_t  m_frame_id;		   //图像帧号
    uint64_t  m_time_stamp;                        //时间戳  单位us
    HLB_Decision m_HLB_Decision;   //远近光灯切换请求
    uint32_t m_HLB_Reason;      	 //远近光灯切换原因, 依据enum HLB_Reason按bit组合
} Perception_HLB_Out_St;

enum FS_Status 
{
    FS_NOT_READY=0,
    FS_NONE=1,		//无失效
    FS_25=2,		//轻度
    FS_50=3,		//中度
    FS_75=4,		//较重度
    FS_99=5		//重度, 失效flag置起
} ;

typedef struct
{
	uint32_t  FS_Datalength;     //Data length of PERCEPTION_FS_OUT
	uint32_t  FS_CRC;            //CRC32-IEEE 802.3
    uint32_t  m_frame_id;			//图像帧号
    uint64_t  m_time_stamp;                                      //时间戳  单位us
    bool m_FS_Free_Sight;	
    FS_Status m_FS_Full_Blockage;		//相机被全遮挡失效
    FS_Status m_FS_Rain;			//雨天失效
    FS_Status m_FS_Fog;			//雾天失效
    FS_Status m_FS_Splashes;		//飞溅失效
    FS_Status m_FS_Sun_Ray;		//光刺失效
    FS_Status m_FS_Low_Sun;		//逆光失效
    FS_Status m_FS_Blur_Image;		//模糊失效
    FS_Status m_FS_Partial_Blockage;	//相机被部分遮挡失效
    FS_Status m_FS_Frozen_Windshield_Lens; //挡风冰冻失效
    FS_Status m_FS_Out_Of_Focus;		//相机失焦失效
} Perception_FS_Out_St;

enum DSTSR_Sign_Shape 
{
    DSTSR_SIGN_SHAPE_UNKNOWN=0,
    DSTSR_SIGN_SHAPE_CIRCLE=1,		//圆形
    DSTSR_SIGN_SHAPE_RECTANGLE=2,		//矩形
    DSTSR_SIGN_SHAPE_TRIANGLE_UP=3,	//上三角形
    DSTSR_SIGN_SHAPE_TRIANGLE_DOWN=4,	//下三角形
    DSTSR_SIGN_SHAPE_DIAMOND=5,		//菱形
    DSTSR_SIGN_SHAPE_PENTAGON=6,		//五边形
    DSTSR_SIGN_SHAPE_RESERVED_2=7,
    DSTSR_SIGN_SHAPE_RESERVED_3=8
} ;

enum DSTSR_Relevancy 
{
    DSTSR_RELEVANCY_RELEVANT_SIGN=0,
    DSTSR_RELEVANCY_HIGHWAY_EXIT_SIGN=1,	//高速出口
    DSTSR_RELEVANCY_OTHER_LANE_SIGN=2,	//其它车道
    DSTSR_RELEVANCY_PARALLEL_ROAD_SIGN=3,	//平行道路
    DSTSR_RELEVANCY_SIGN_ON_TURN=4,	//转弯场景
    DSTSR_RELEVANCY_FAR_IRRELEVANT_SIGN=5,	//远距离无关
    DSTSR_RELEVANCY_INTERNAL_SIGN_CONTRADICTION=6,  //内部标识矛盾
    DSTSR_RELEVANCY_EMBEDDED=7,		//内嵌
    DSTSR_RELEVANCY_ON_TRUCK=8,		//卡车上
    DSTSR_RELEVANCY_REGION_CODE_CONTRUDICTION=9,   //区码矛盾
    DSTSR_RELEVANCY_DELAY=10,			//延时
    DSTSR_RELEVANCY_OTHER_REASON=11		//其它原因
} ;

enum DSTSR_Sign_Name
{
   e_std_10 = 0,    //限速10kph
   e_std_20 = 1, //限速20kph
   e_std_30 = 2,    //限速30kph
   e_std_40 = 3,    //限速40kph
   e_std_50 = 4,    //限速50kph
   e_std_60 = 5, //限速60kph
   e_std_70 = 6,    //限速70kph
   e_std_80 = 7,  //限速80kph
   e_std_90 = 8,    //限速90kph
   e_std_100 = 9,  //限速100kph
   e_std_110 = 10,   //限速110kph
   e_std_120 = 11,   //限速120kph
   e_std_130 = 12,   //限速130kph
   e_std_140 = 13,   //限速140kph
   e_car_limit = 23,  //轿车禁行
   e_carUpMotorDownDiagonal = 24,  //摩托车和轿车禁行
   e_minimum_SL = 25,   //摩托车禁行
   e_leftOrStraight = 27,   //直行左转
   e_lgt_10 = 28,  // LED限速10kph
   e_lgt_20 = 29,  // LED限速20kph
   e_lgt_30 = 30,  // LED限速30kph
   e_lgt_40 = 31,  // LED限速40kph
   e_lgt_50 = 32,  // LED限速50kph
   e_lgt_60 = 33,  // LED限速60kph
   e_lgt_70 = 34,  // LED限速70kph
   e_lgt_80 = 35,  // LED限速80kph
   e_lgt_90 = 36,  // LED限速90kph
   e_lgt_100 = 37, // LED限速100kph
   e_lgt_110 = 38, // LED限速110kph
   e_lgt_120 = 39, // LED限速120kph
   e_lgt_130 = 40, // LED限速130kph
   e_lgt_140 = 41, // LED限速140kph
   e_rightOrStraight = 45, //直行右转
   e_std_noTurn_on_red = 46, //红灯禁止转向
   e_Oncoming_Priority = 47, //对向来车优先
   e_noU_Turn = 48, //禁止掉头
   e_endOfChildren = 51, //
   e_atPedestriansCrossing = 52, //人行横道
   e_rectBump = 53, //前方减速带
   e_dividedHighWay = 54, //
   e_lowClearance = 57, //
   e_PedestrianLane = 59, //人行道
   e_pedLimit = 60, //禁止行人
   e_pedLimitDiagonal = 61, //禁止行人(带斜线)
   e_SharedLane = 62, //
   e_SharedSeparateLane = 63, //
   e_std_end_general = 64, //解除限速
   e_lgt_end_general = 65, //LED解除限速
   e_endOfDiversion = 66, //
   e_std_end_noParking_zone = 77, //解除禁停区
   e_ausfahrt = 78, //
   e_std_end_ded_two_digits = 79, //两位数解除限速
   e_std_end_ded_three_digits = 80, //三位数解除限速
   e_lgt_end_ded_two_digits = 81, //LED两位数解除限速
   e_lgt_end_ded_three_digits = 82, //LED三位数解除限速
   e_std_150 = 85, //限速150kph
   e_std_160 = 86, //限速160kph
   e_reverseCurveLeft = 95, //
   e_reverseCurveRight = 96, //
   e_sharpCurveLeft = 97, //
   e_sharpCurveRight = 98, //
   e_std_5 = 100, //限速5kph
   e_std_15 = 101, //限速15kph
   e_std_25 = 102, //限速25kph
   e_std_35 = 103, //限速35kph
   e_std_45 = 104, //限速45kph
   e_std_55 = 105, //限速55kph
   e_std_65 = 106, //限速65kph
   e_std_75 = 107, //限速75kph
   e_std_85 = 108, //限速85kph
   e_std_95 = 109, //限速95kph
   e_std_105 = 110, //限速105kph
   e_std_115 = 111, //限速115kph
   e_std_125 = 112, //限速125kph
   e_std_135 = 113, //限速135kph
   e_std_145 = 114, //限速145kph
   e_lgt_5 = 115, //LED限速5kph
   e_lgt_15 = 116, //LED限速15kph
   e_lgt_25 = 117, //LED限速25kph
   e_lgt_35 = 118, //LED限速35kph
   e_lgt_45 = 119, //LED限速45kph
   e_lgt_55 = 120, //LED限速55kph
   e_lgt_65 = 121, //LED限速65kph
   e_lgt_75 = 122, //LED限速75kph
   e_lgt_85 = 123, //LED限速85kph
   e_lgt_95 = 124, //LED限速95kph
   e_lgt_105 = 125, //LED限速105kph
   e_lgt_115 = 126, //LED限速115kph
   e_lgt_125 = 127, //LED限速125kph
   e_bewareOfSnow = 131, //
   e_bicycleCrossing = 132, //注意两轮车穿行
   e_buses_trams = 133, //注意公交车
   e_children = 134, //注意儿童
   e_congestionHazard = 135, //注意拥堵危险
   e_curveLeft = 136, //注意前方左弯
   e_curveRight = 137, //注意前方右弯
   e_doubleCurveLeft = 139, //注意前方连续左弯
   e_doubleCurveRight = 140, //注意前方连续右弯
   e_drawBridge = 141, //注意前方吊桥
   e_fallingRocks = 142, //注意前方落石
   e_generalDanger = 143, //注意危险
   e_guardedRailwayCrossing = 144, //注意前方铁路围栏
   e_intersection = 145, //
   e_leftMerge = 146, //注意左侧汇车
   e_looseGravel = 147, //注意碎石
   e_lowFlyingAircraft = 148, //注意低飞飞行器
   e_pedestrians = 149, //注意行人
   e_pedestriansCrossing = 150, //注意行人横穿
   e_priority = 151, //
   e_rightMerge = 152, //
   e_roadWorkAhead = 153, //
   e_roadNarrows = 154, //注意两侧道路变窄
   e_roadNarrowsLeft = 155, //注意左侧道路变窄
   e_roadNarrowsRight = 156, //注意右侧道路变窄
   e_roadWork = 157, //注意道路施工
   e_roughRoad = 158, //注意凹凸路面
   e_roundabout = 159, //注意环岛
   e_slipperyWhenWet = 160, //注意易侧滑
   e_steepDowngrade = 161, //注意陡峭下坡路
   e_steepUpgrade = 162, //注意陡峭上坡路
   e_strongCrossWind = 163, //注意强横风
   e_trafficSignals = 164, //注意红路灯
   e_twoWayTraffic = 165, //注意双向交通
   e_unguardedRailwayCrossing = 166, //注意无防护铁道口
   e_wildAnimalCrossing = 167, //注意野生动物
   e_yield = 168, //注意礼让
   e_priorityRoad = 169, //
   e_endofPriorityRoad = 170, //
   e_std_motorWay = 171, //
   e_std_endoffMotorWay = 172, //
   e_std_expressWay = 173, //
   e_std_endoffExpressWay = 174, //
   e_std_residentialArea = 175, //住宅区域
   e_std_endofResidentialArea = 176, //结束住宅区域
   e_std_cityEntrance = 177, //
   e_std_cityEntranceCombined = 178, //
   e_addLeft = 180, //
   e_addRight = 181, //
   e_laneEndsLeft = 182, //
   e_laneEndsRight = 183, //
   e_exitRight = 184, //
   e_cityEntranceCN = 185, //
   e_camera = 186, //
   e_laneMergeLeftTxt = 187, //
   e_laneMergeRightTxt = 188, //
   e_RectOncomingPriority = 189, //对向优先
   e_laneSplitRight = 190, //
   e_windingLeft = 191, //
   e_windingRight = 192, //
   e_SideRoadLeft = 193, //左侧小路
   e_SideRoadRight = 194, //右侧小路
   e_thruTrafficMerge = 195, //
   e_stopAhead = 196, //
   e_LooseShoulder = 197, //
   e_std_no_entrance = 199, //禁止进入
   e_std_np_start = 200, //禁止超车
   e_std_np_end = 201, //取消禁止超车
   e_std_np_truck_start = 202, //禁止卡车超车
   e_std_np_truck_end = 203, //取消禁止卡车超车
   e_ca_end_road_work = 205, //结束道路施工
   e_ca_end_construction = 206, //结束施工区域
   e_std_stopSign = 210, //禁止停车
   e_std_truckLimit = 211, //卡车限长
   e_crossRoads = 212, //
   e_SideRoad = 213, //
   e_roadWorkAheadTxt = 214, //
   e_roadConstructionAheadTxt = 215, //
   e_bump = 217, //注意前方减速带
   e_end_school_zone = 218, //结束学校区域
   e_std_CityEntrance_Black_BG = 219, //
   e_lgt_np_start = 220, //LED禁止超车
   e_lgt_np_end = 221, //LED取消禁止超车
   e_std_BuiltUpArea = 222, //前方城市区域
   e_std_endofBuiltUpArea = 223, //前方结束城市区域
   e_std_roundabout = 224, //前方环岛
   e_lgt_np_truck_start = 225, //LED禁止卡车超车
   e_lgt_np_truck_end = 226, //LED取消禁止卡车超车
   e_std_endOfCityEntrance = 229, //
   e_std_arrow_straight = 240, //直行指示牌
   e_std_arrow_right = 241, //右箭头指示牌
   e_std_arrow_left = 242, //左箭头指示牌
   e_std_arrow_rightAhead = 243, //右转指示牌
   e_std_arrow_leftAhead = 244, //左转指示牌
   e_std_arrow_noLeft = 245, //禁止左转
   e_std_arrow_noRight = 246, //禁止右转
   e_std_arrow_KeepLeft = 247, //靠左行驶
   e_std_arrow_KeepRight = 248, //靠右行驶
   e_std_arrow_eitherSide = 249, //靠两边行驶
   e_std_roadClosed = 250, //道路封闭
   e_BicycleLane = 256, //自行车道
   e_bicycleLimit = 257, //禁止自行车
   e_busLimit = 258, //禁止公交车
   e_hazardousTruckLimit = 259, //禁止危险卡车
   e_heightLimit = 260, //限高
   e_parking = 262, //禁停
   e_pedBicycleLimit = 263, //禁止行人和自行车
   e_trucksOnly = 265, //仅卡车
   e_weightLimit = 266, //限重
   e_widthLimit = 267, //限宽
   e_motorUpCarDown = 268, //
   e_lowEmissionZone = 269, //低排放区域
   e_endOfLowEmissionZone = 270, //结束低排放区域
   e_tollRoad = 271, //收费道路
   e_std_AV_vertical = 277, //
   e_std_AV_horizontal = 278, //
   e_std_Keep_Distance = 301, //保持车距
   e_std_Load_Limit = 302, //限载重
   e_std_Bus_Lane = 303, //公交车道
   e_std_Tram_Lane = 304, //有轨电车道
   e_std_End_Bus_Lane = 305, //结束公交车道
   e_std_No_straight = 307, //禁止直行
   e_std_U_Turn = 308, //掉头
   e_std_End_tollRoad = 309, //结束收费路
   e_std_End_Limit_HazardousTruck = 312, //结束危险卡车限行
   e_std_etcJP = 313, //日本电子ETC收费
   e_std_etcTollJP = 314, //日本ETC/人工收费
   e_std_tollJP = 315, //日本人工收费
   e_std_arrowRightJP = 316, //
   e_std_arrowLeftJP = 317, //
   e_std_directionalJP = 318, //
   e_std_roadworkJP = 319, //
   e_std_construction_rightJP = 320, //
   e_std_roadwork_electJP = 321, //
   e_std_roadwork_rightJP = 322, //
   e_std_one_way = 325, //单行道
   e_std_endof_one_way = 326, //结束单行道
   e_std_lanes_topology  = 333, //道路拓扑
   e_exitLeft = 340, //
   e_pass_left_or_right = 342, //
   e_korea_slow = 344, //
   e_school_zone = 350, //学校区域
   e_school_bus_stop_ahead = 351, //前方校车停靠点
   e_prepared_to_stop = 353, //
   e_hairpinToLeft = 359, //
   e_laneSplitLeft = 360, //
   e_hairpinToRight = 361, //
   e_T_Roads = 362, //
   e_2_lanesReverse_left = 366, //
   e_2_lanesReverse_right = 367, //
   e_3_lanesReverse_left = 368, //
   e_3_lanesReverse_right = 369, //
   e_MergeToMainFromRight = 370, //
   e_offset_roads_Right_Left = 372, //
   e_offset_roads_Left_Right = 373, //
   e_railWayCrossingOnLeft = 374, //
   e_railWayCrossingOnRight = 375, //
   e_thruTrafficMergeLeft = 376, //
   e_thruTrafficMergeRight = 377, //
   e_ShareRoadsPedestBikes = 378, //
   e_ShareRoadsCarsBikes = 379, //
   e_dividedHighWay_End = 381, //
   e_accidentSpot = 382, // 
   e_narrow_bridge = 383, //
   e_detour_ahead = 384, //
   e_sharp_deviation_left = 392, //
   e_sharp_deviation_right = 393, //
   e_level_crossing = 395, //
   e_elecOff = 399, //
   e_sign_unknown = 0xffff       //未知类型
};

enum DSTSR_Sup1_SignName
{
   e_none = 0,   //
   e_rain = 1,    //
   e_snow = 2,  //
   e_trailer = 3, //
   e_time = 4,   //
   e_Arrow_left = 5,      //
   e_Arrow_right = 6,   //
   e_BendArrow_left = 7, //
   e_BendArrow_right = 8,  //
   e_truck = 9, //
   e_distance_arrow = 10, //
   e_weight = 11, //
   e_distance_in = 12,   //
   e_tractor = 13, //
   e_snow_rain = 14, //
   e_school = 15, //
   e_rain_cloud = 16, //
   e_fog = 17, //
   e_hazardous_materials = 18, //
   e_night = 19, //
   e_supp_sign_generic = 20, //
   e_rappel = 21, //
   e_zone = 22, //
   e_ramp = 23, //闸道
   e_end = 24, //结束(限速等)
   e_exit = 25,  //出口
   e_advisory = 26, //
   e_minimum = 27, //最小限速
   e_reduced_ahead = 28, //
   e_distance_stop = 29, //
   e_par_verglas = 30, //
   e_ahead = 31, //
   e_area = 32, //
   e_road_work_au = 33, //
   e_arrow_bidirectional = 34, //
   e_work_zone = 35, //
   e_distance_in_for = 36, //
   e_zone_end = 37, //
   e_supp_end_school_zone = 38, //
   e_supp_camera = 39, //
   e_larmschutz = 40, //
   e_car = 41, //
   e_shared_zone = 42, //
   e_supp_bump = 43, //
   e_snow_rain_dis_arrow = 44, //
   e_snow_truck = 45, //
   e_motorcycle = 46, //
   e_time_school = 47, //
   e_truck_bus = 48, //
   e_koko_made = 49, //     
   e_koko_kara = 50, //
   e_sup_sign_unknown = 0xff   //未知附加类型
};

typedef struct
{
    uint8_t m_DSTSR_ID;			                  //交通标识ID  1-127
    DSTSR_Sign_Name  m_DSTSR_Sign_Name;                	 //交通标识分类名称
    float m_DSTSR_Sign_Long_Distance;		                  //交通标识纵向距离，单位m
    float m_DSTSR_Sign_Lat_Distance;		                  //交通标识横向距离，单位m
    float m_DSTSR_Sign_Height;		                  //交通标识高度，单位m
    DSTSR_Sign_Shape m_DSTSR_Sign_Shape;                 	 //交通标识形状
    DSTSR_Relevancy m_DSTSR_Relevancy; 	                  //交通标识关联
    float m_DSTSR_Sup1_Confidence;		                  //交通标识附加分类置信度
    float m_DSTSR_Confidence;			                  //交通标识分类置信度
    float m_DSTSR_Relevancy_Confidence;		  //关联性置信度
    uint32_t m_DSTSR_Tracking_Out_of_Image;		  //出FOV视野的累计帧数
    DSTSR_Sup1_SignName m_DSTSR_Sup1_SignName; 	//交通标识附加分类名称
}TSR_Item_St;

typedef struct
{
	uint32_t  DSTSR_Datalength;     //Data length of PERCEPTION_DSTSR_OUT
	uint32_t  DSTSR_CRC;            //CRC32-IEEE 802.3
    uint32_t  m_frame_id;			                  //图像帧号
    uint64_t  m_time_stamp;                                                       //时间戳  单位us
    uint8_t    m_tsr_num;                                                            //标志牌个数
    TSR_Item_St  m_TSR_Item[TSR_OBJ_MAX_NUM]; 	//标志牌目标详细信息
} Perception_DSTSR_Out_St;

enum LA_Availability_State 
{
    LA_AVAILABILITY_NOT_AVAILABLE=0,
    LA_AVAILABILITY_PREDICATED=1,    //预测
    LA_AVAILABILITY_DETECTED=2        //检测
} ;

enum LA_Lanemark_Type 
{
    LA_LANEMARK_UNDECIDED=0,
    LA_LANEMARK_SOLID=1,		//实线
    LA_LANEMARK_DASHED=2,	//虚线
    LA_LANEMARK_DLM=3,		//双线
    LA_LANEMARK_BOTTS=4,		//点虚
    LA_LANEMARK_DECELERATION=5,	//减速线
    LA_LANEMARK_HOV_LANE=6	//HOV线
} ;

enum LA_Line_Side 
{
    LA_LINE_SIDE_NONE=0,
    LA_LINE_SIDE_LEFT_LEFT_LANEMARK=1,	//左车道左线
    LA_LINE_SIDE_LEFT_RIGHT_LANEMARK=2,	//左车道右线
    LA_LINE_SIDE_RIGHT_LEFT_LANEMARK=3,	//右车道左线
    LA_LINE_SIDE_RIGHT_RIGHT_LANEMARK=4,	//右车道右线
    LA_LINE_SIDE_RIGHT_NEXT_NEXT=5,		
    LA_LINE_SIDE_LEFT_NEXT_NEXT=6
} ;

typedef struct
{
	uint8_t LA_Track_ID;  //ID of the lane mark model
    float m_LA_Confidence;				//相邻车道线置信度
    LA_Availability_State m_LA_Availability_State;		//相邻车道线状态
    float m_LA_View_Range_Start;			//相邻车道线起始点
    float m_LA_View_Range_End;			//相邻车道线结束点
    LA_Lanemark_Type m_LA_Lanemark_Type;		//相邻车道线类型
    LA_Line_Side m_LA_Line_Side;			//相邻车道线分边
    float m_LA_Line_C3;				//三次多项式三次项系数
    float m_LA_Line_C2;				//三次多项式二次项系数
    float m_LA_Line_C1;				//三次多项式一次项系数
    float m_LA_Line_C0;				//三次多项式常数项
}LA_Line_St;

typedef struct
{
	uint32_t  LA_Datalength;     //Data length of PERCEPTION_LA_OUT
	uint32_t  LA_CRC;            //CRC32-IEEE 802.3
    uint32_t  m_frame_id;				//图像帧号
    uint64_t  m_time_stamp;                                                     //时间戳  单位us
    uint8_t    m_adj_line_num;                                                   //邻近车道线个数

    LA_Line_St  m_adj_line[ADJ_LINE_MAX_NUM];                  //邻近车道线详细信息
} Perception_LA_Out_St;

enum LRE_Availability_State 
{
    LRE_AVAILABILITY_NOT_AVAILABLE=0,
    LRE_AVAILABILITY_PREDICATED=1,		 //预测
    LRE_AVAILABILITY_DETECTED=2		//检测
} ;

enum LRE_Side 
{
    LRE_SIDE_UNFILLED=0,
    LRE_SIDE_LEFT=1,			//左侧路沿
    LRE_SIDE_RIGHT=2			//右侧路沿
} ;

typedef struct
{
	uint8_t LRE_Track_ID;  //ID of the lane boundary model
    float m_LRE_Confidence;				//路沿置信度
    LRE_Availability_State m_LRE_Availability_State;	//路沿状态
    float m_LRE_View_Range_Start;			//路沿起始位置
    float m_LRE_View_Range_End;			//路沿结束位置
    float m_LRE_Line_C3;				//三次多项式三次项系数
    float m_LRE_Line_C2;				//三次多项式二次项系数
    float m_LRE_Line_C1;				//三次多项式一次项系数
    float m_LRE_Line_C0;				//三次多项式常数项
    LRE_Side m_LRE_Side;				//路沿分边
}LRE_Line_St;

typedef struct
{
	uint32_t  LRE_Datalength;     //Data length of PERCEPTION_LRE_OUT
	uint32_t  LRE_CRC;            //CRC32-IEEE 802.3
    uint32_t  m_frame_id;				//图像帧号
    uint64_t  m_time_stamp;                                                     	//时间戳  单位us
    uint8_t    m_roadedge_num;                                               //路沿个数
    LRE_Line_St  m_roadedge_line[ROAD_EDGE_MAX_NUM];      //路沿的详细信息
} Perception_LRE_Out_St;

enum APP_Main_State_em
{
    APP_Main_State_UNKNOWN=0x00,
    APP_Main_State_Initialization=0x01,
    APP_Main_State_Pending_Vision=0x11,
    APP_Main_State_Running_Vision=0x12,
    APP_Main_State_Pending_TAC2=0x21,
    APP_Main_State_TAC2=0x22,
    APP_Main_State_Pending_CTAC=0x31,
    APP_Main_State_CTAC=0x32,
    APP_Main_State_Pending_SPC=0x41,
    APP_Main_State_SPC=0x42,
    APP_Main_State_Pending_MTF=0x51,
    APP_Main_State_MTF=0x52
} ;

enum APP_Cam_State_em
{
    APP_Cam_State_Not_connected=0,
    APP_Cam_State_Connected=1
} ;

typedef struct
{
	uint32_t  APP_Datalength;     //Data length of PERCEPTION_APP_OUT
	uint32_t  APP_CRC;            //CRC32-IEEE 802.3
    uint32_t  APP_Frame_ID;				//图像帧号
    uint64_t  APP_Timestamp;                                                     	//时间戳  单位us
    APP_Main_State_em  APP_Main_State;      //感知软件主状态
	APP_Cam_State_em  APP_Cam_State;      //镜头模组状态
    float APP_Cam_Temperature;			//镜头模组温度
    float APP_Sensor_Framerate;			//检测到的镜头模组有效帧率
    float APP_Perception_Framerate;			//感知输出的有效帧率
	float APP_Latency;			//延迟，从曝光到输出结果的时间差
} Perception_APP_Out_St;

enum AF_AutoCamCalibStatus_em {
  AF_AUTO_CALIB_OK  = 0x0, //标定成功
  AF_AUTO_CALIB_USING_CURRENT_FRAME = 0x1, //当前帧有效， 标定中
  AF_AUTO_CALIB_LANE_UNSUFFIENT = 0x2, //未检测车道线或数量不足
  AF_AUTO_CALIB_LANE_CURVE_DETECT = 0x3, //检测到车道线弯曲
  AF_AUTO_CALIB_LANE_EVALUTE_ERROR = 0x4, //车道线点分布异常
  AF_AUTO_CALIB_TRAVEL_NOT_STRAIGHT = 0x5, //车辆未在直行
  AF_AUTO_CALIB_TRAVEL_NOT_IN_MIDDLE = 0x6, //车辆未居中
  AF_AUTO_CALIB_TRAVEL_TOO_SLOW = 0x7, //车速低于要求
  AF_AUTO_CALIB_FAIL_INIT_FALSE = 0x8, //内参初始化错误
  AF_AUTO_CALIB_FAIL_STATUS_UNSATISFY = 0x9, //未分类的错误
  AF_AUTO_CALIB_FAIL_TIME_OUT = 0xA, //标定超时错误
  AF_AUTO_CALIB_FAIL_CHANGELANE = 0xB, //标定过程中换道
  AF_AUTO_CALIB_FAIL_CURVE = 0xC, //弯道过多
  AF_AUTO_CALIB_FAIL_WHEEL = 0xD, //车辆转向
  AF_AUTO_CALIB_FAIL_JOLT = 0xE, //路面颠簸
  AF_AUTO_CALIB_FAIL_ROCK = 0xF, //车辆左右摇晃明显
  AF_AUTO_CALIB_FAIL_RET_OUT_RANGE_PITCH = 0x10, //俯仰角超差
  AF_AUTO_CALIB_FAIL_RET_OUT_RANGE_YAW = 0x11, //偏航角超差
  AF_AUTO_CALIB_FAIL_RET_OUT_RANGE_ROLL = 0x12, //滚转角超差
  AF_AUTO_CALIB_INIT_DONE = 0x13, //初始化完成
};

typedef struct{
  float cam_tx;        //相机x坐标，单位m, 基于车辆后轴中心地面坐标系
  float cam_ty;        //相机y坐标， 单位m, 基于车辆后轴中心地面坐标系
  float cam_tz;        //相机z坐标， 单位m, 基于车辆后轴中心地面坐标系
  float cam_pitch;   //相机pitch角度，单位deg， 按右手坐标系
  float cam_yaw;    //相机yaw角度, 单位deg， 按右手坐标系
  float cam_roll;     //相机roll角度，单位deg， 按右手坐标系
  float Twc[4][4];  // 相机外参矩阵
}AF_CamCalibResult_St;  //相机标定结果

typedef struct
{
	uint32_t  AF_Datalength;     //Data length of PERCEPTION_AF_OUT
	uint32_t  AF_CRC;            //CRC32-IEEE 802.3
    uint32_t  AF_Frame_ID;				//图像帧号
    uint64_t  AF_Timestamp;                                                     	//时间戳  单位us
    AF_AutoCamCalibStatus_em AF_calib_status;   //标定状态
    uint8_t  AF_calib_progress;   //标定进度  0~100
    AF_CamCalibResult_St AF_calib_result;   //标定结果
} Perception_AF_Out_St;

typedef struct
{
	Perception_APP_Out_St           Perception_APP_Out;         //感知软件基础信息   对应 Perception_APP_Out_St
    Perception_Dyn_OBJ_Out_St       Perception_DYN_OBJ_Out; 	//动态目标消息  对应 Perception_Dyn_OBJ_Out_St
    Perception_Static_Obj_Out_St    Perception_STATIC_OBJ_Out;	//静态目标消息  对应 Perception_Static_OBJ_Out_St
    Perception_FCF_Out_St           Perception_FCF_Out;		//FCF消息  对应 Perception_FCF_Out_St
    Perception_LH_Out_St            Perception_LH_Out;		//本车道消息  对应 Perception_LH_Out_St
    Perception_HLB_Out_St           Perception_HLB_Out;		//HLB消息    对应 Perception_HLB_Out_St
    Perception_FS_Out_St            Perception_FS_Out;		//FailSafe消息  对应 Perception_FS_Out_St
    Perception_DSTSR_Out_St         Perception_DSTSR_Out;		//TSR消息 对应 Perception_DSTSR_Out_St
    Perception_LA_Out_St            Perception_LA_Out;		//邻近车道消息  对应 Perception_LA_Out_St
    Perception_LRE_Out_St           Perception_LRE_Out;		//路沿消息 对应 Perception_LRE_Out_St
    Perception_AF_Out_St            Perception_AF_Out;		//Autofix消息 对应 Perception_AF_Out_St	
} Perception_MESSAGE_Out_St;


enum Perception_MessageType : uint32_t 
{
	PERCEPTION_MESSAGE_OUT,         //感知软件输出物大结构体
};

enum Perception_Init_Error_em
{
    APP_Init_Error_Init_CRC_FAULT=(1<<0), //(BIT_0)
    APP_Init_Error_Init_PARA_OOR=(1<<1), //(BIT_1)
	APP_Init_Error_IntrisicCal_OOR=(1<<2) //(BIT_2)
} ;

enum Perception_Diag_Error_em
{
    APP_Diag_Error_VIN_Timeout=(1<<0), //(BIT_0)
    APP_Diag_Error_VIN_CRC_FAULT=(1<<1), //(BIT_1)
    APP_Diag_Error_VIN_RFC_FAULT=(1<<2), //(BIT_2)
    APP_Diag_Error_CAMERA_CAPTURE_INTERFACE_FAULT=(1<<3), //(BIT_3)
    APP_Diag_Error_CAMERA_CAPTURE_TIMEOUT_FAULT=(1<<4), //(BIT_4)
    APP_Diag_Error_CAMERA_FRAMERATE_FAULT=(1<<5), //(BIT_5)
    APP_Diag_Error_CAMERA_IMAGEFORMAT_FAULT=(1<<6), //(BIT_6)
    APP_Diag_Error_PERCEPTION_CAPTURE_INTERFACE_FAULT=(1<<7), //(BIT_7)
    APP_Diag_Error_PERCEPTION_CAPTURE_TIMEOUT_FAULT=(1<<8), //(BIT_8)
    APP_Diag_Error_PREPROCESS_HW_FAULT=(1<<9), //(BIT_9)
    APP_Diag_Error_INFERENCE_HW_FAULT=(1<<10), //(BIT_10)
    APP_Diag_Error_POSTPROCESS_HW_FAULT=(1<<11), //(BIT_11)
    APP_Diag_Error_ALGORITHM_INNERCALLFUNC_FAULT=(1<<12), //(BIT_12)
	APP_Diag_Error_MEMORY_ALLOCATION_FAULT=(1<<13), //(BIT_13)
} ;

typedef struct
{
	Perception_Init_Error_em  Perception_Init_Error;      //感知软件自检的初始化错误
	Perception_Diag_Error_em  Perception_Diag_Error;      //感知软件自检的故障
} Perception_Diag_St;


#pragma pack(pop)  //恢复之前保存的对齐状态

#ifdef __cplusplus
}
#endif

#endif // PERCEPTION_OUT_MESSAGES_H_
