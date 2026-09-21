#pragma once

#include <cstdint>
#include <string>
#include <utility>
#include <vector>

namespace gf_foxglove {

constexpr float kDWorkM = 120.0f;
constexpr float kDBevM = 130.0f;
constexpr float kAdcXMinM = -35.0f;  // FS rear tip / meter-window rear (contract)
constexpr float kAdcXMaxM = 120.0f;
constexpr int kBevW = 400;
constexpr int kBevH = 800;
constexpr float kBevCamBackM = 35.0f;  // match env#2 bev_afc / afc bev.mount
constexpr float kBevCamHeightM = 40.0f;
constexpr float kBevCamLookM = 60.0f;
// Camera behind rear FS tip (−35) so closing bar is in front of cam (visible).
// Meter window stays x∈[−35,+120]; CamBack > 35.
// Observer pose: config/{afc,adc}/bev.mount.json (GF_MOUNTS_JSON / GF_BEV_SKU).
constexpr float kAdcCamBackM = 45.0f;
constexpr float kAdcCamHeightM = 48.0f;
constexpr float kAdcCamLookM = 40.0f;
constexpr float kDashOnM = 6.0f;
constexpr float kDashGapM = 9.0f;
constexpr float kDashPeriodM = kDashOnM + kDashGapM;
constexpr float kSeeHostLatM = 1.5f;  // AFC occupy opening only
constexpr float kSeeFovDeg = 100.0f;  // AFC optical_d; = camera_contract front.fov
constexpr int kMaxHostLanes = 2;
constexpr int kMaxAdjLanes = 4;
constexpr int kMaxLreEdges = 2;
constexpr int kMaxDynObj = 13;
constexpr int kMaxSurroundObj = 16;
constexpr int kMaxParkingSlots = 8;
constexpr int kFsEmptyN = 180;
constexpr int kMaxTrajPts = 60;

// Single meter-window for paint/camera (SKU). Grey lanes follow VR_End on +x.
struct BevWindow {
  float x_min = 0.0f;
  float x_max = kDBevM;
};

struct Rgb {
  std::uint8_t r, g, b;
};

/** Cubic on +x (trusted VR); behind ego: linear c0+c1·x — same as planning RoadEdgeYFwd. */
inline float PolyYAt(float x, float c0, float c1, float c2, float c3) {
  if (x < 0.0f) {
    return c0 + c1 * x;
  }
  return c0 + c1 * x + c2 * x * x + c3 * x * x * x;
}

struct HostLanePoly {
  int side = 0;
  float c0 = 0, c1 = 0, c2 = 0, c3 = 0;
  float x0 = 0;
  float x1 = kDBevM;
  int lanemark_type = 1;
  float y_at(float x) const { return PolyYAt(x, c0, c1, c2, c3); }
  bool is_dashed() const { return lanemark_type == 2; }
};

struct AdjLanePoly {
  int side = 0;
  float c0 = 0, c1 = 0, c2 = 0, c3 = 0;
  float x0 = 0;
  float x1 = kDBevM;
  int lanemark_type = 2;
  float y_at(float x) const { return PolyYAt(x, c0, c1, c2, c3); }
  bool is_dashed() const { return lanemark_type != 1; }
};

/** Physical road edge (LRE). Distinct from LH/LA paint. */
struct LreEdgePoly {
  int side = 0;  // 1=left 2=right
  float c0 = 0, c1 = 0, c2 = 0, c3 = 0;
  float x0 = 0;
  float x1 = kDBevM;
  float y_at(float x) const { return PolyYAt(x, c0, c1, c2, c3); }
};

struct BevDynObj {
  int obj_id = 0;
  float x_m = 0;
  float y_m = 0;
  bool is_cipv = false;
  int obj_class = 0;
  float length_m = 4.5f;
  float width_m = 1.8f;
  float heading_rad = 0;
};

struct BevParkingSlot {
  float x_m = 0;
  float y_m = 0;
  float yaw_rad = 0;
  float length_m = 5.0f;
  float width_m = 2.5f;
  bool free = true;
};

struct LiveBevState {
  std::uint64_t t_ns = 0;
  float speed_mps = 0;
  float yaw_rate_degps = 0;
  float steer_angle_deg = 0;
  int gear = 0;
  float traj_x[kMaxTrajPts]{};
  float traj_y[kMaxTrajPts]{};
  float traj_v[kMaxTrajPts]{};
  int n_traj = 0;
  int n_traj_v = 0;
  float traj_d_see_m = 0;
  float traj_t_plan_s = 0;
  float traj_v_plan_mps = 0;
  float traj_horizon_m = 0;
  float traj_s_stop_m = 0;   // from Trajectory; ~cap = inactive
  float v_sign_max_mps = 0;  // 0 = none; from Trajectory
  float v_sign_min_mps = 0;
  // Light HUD: 0=none, 164=yellow, 196=red, 198=green (DSTSR Relevant).
  int light_sign_name = 0;
  bool allow_lc = false;
  float nearest_cm = -1;  // <0 = none
  float odom_m = 0;
  std::uint64_t last_t_ns = 0;
  float last_speed_mps = 0;
  float lon_accel_mps2 = 0;
  float throttle_cmd = 0;
  float brake_cmd = 0;
  bool has_perc_lead = false;
  bool has_perc_lanes = false;
  HostLanePoly host_lanes[kMaxHostLanes];
  int n_host = 0;
  AdjLanePoly adj_lanes[kMaxAdjLanes];
  int n_adj = 0;
  LreEdgePoly lre_edges[kMaxLreEdges];
  int n_lre = 0;
  float lane_width_m = 3.5f;
  BevDynObj perc_objects[kMaxDynObj];
  int n_obj = 0;
  BevDynObj surround_objects[kMaxSurroundObj];
  int n_surround = 0;
  BevParkingSlot parking_slots[kMaxParkingSlots];
  int n_slot = 0;
  int cipv_id = 0;
  float lead_dist_m = 0;
  float cipo_x_m = 0;
  float cipo_y_m = 0;
  // Driving fused Freespace vs surround Near (separate buffers — no stomping).
  bool has_fs_plan = false;
  float fs_plan_d_lane_fwd_m[3]{};  // host/left/right clear
  uint8_t fs_plan_n_poly = 0;
  float fs_plan_poly_x_m[180]{};
  float fs_plan_poly_y_m[180]{};
  bool has_fs_near = false;
  float fs_near_d_r_m[kFsEmptyN]{};
  uint8_t fs_near_type[kFsEmptyN]{};
  // ParkingTrajectory owns path → parking BEV (Near contour); else driving.
  bool parking_view = false;
};

bool dash_lit_m(float s_m, float scroll_m = 0.0f);
Rgb color_for_obj_id(int obj_id);
Rgb traj_color_for_v(float v, float v_hi = 12.0f);
float see_opening_m(float host_vr_m, const LiveBevState& st);  // AFC ruler
float driving_see_m(const LiveBevState& st, float host_vr_m);   // AFC ruler
void advance_odom(LiveBevState& st, std::uint64_t t_ns, float speed_mps);

// Portrait 400×800 PNG. Gold paint for SIL gf_foxglove_ws and Host gf_host_bev_ws.
// GF_BEV_SKU=adc → x∈[-35,+120]; default/afc → forward-biased AFC frame.
std::string render_ego_bev_png(const LiveBevState& st, int width = kBevW, int height = kBevH);

bool bev_sku_is_adc();
BevWindow bev_window();

}  // namespace gf_foxglove
