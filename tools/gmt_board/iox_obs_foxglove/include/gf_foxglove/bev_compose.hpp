#pragma once

#include <cstdint>
#include <string>
#include <utility>
#include <vector>

namespace gf_foxglove {

constexpr float kDWorkM = 120.0f;
constexpr float kDBevM = 130.0f;
constexpr int kBevW = 400;
constexpr int kBevH = 800;
constexpr float kBevCamBackM = 22.0f;
constexpr float kBevCamHeightM = 40.0f;
constexpr float kBevCamLookM = 60.0f;
constexpr float kDashOnM = 6.0f;
constexpr float kDashGapM = 9.0f;
constexpr float kDashPeriodM = kDashOnM + kDashGapM;
constexpr float kSeeHostLatM = 1.5f;
constexpr float kSeeFovDeg = 50.0f;
constexpr int kMaxHostLanes = 2;
constexpr int kMaxAdjLanes = 4;
constexpr int kMaxDynObj = 13;
constexpr int kMaxTrajPts = 60;

struct Rgb {
  std::uint8_t r, g, b;
};

struct HostLanePoly {
  int side = 0;
  float c0 = 0, c1 = 0, c2 = 0, c3 = 0;
  float x0 = 0;
  float x1 = kDBevM;
  int lanemark_type = 1;
  float y_at(float x) const { return c0 + c1 * x + c2 * x * x + c3 * x * x * x; }
  bool is_dashed() const { return lanemark_type == 2; }
};

struct AdjLanePoly {
  int side = 0;
  float c0 = 0, c1 = 0, c2 = 0, c3 = 0;
  float x0 = 0;
  float x1 = kDBevM;
  int lanemark_type = 2;
  float y_at(float x) const { return c0 + c1 * x + c2 * x * x + c3 * x * x * x; }
  bool is_dashed() const { return lanemark_type != 1; }
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
  float lane_width_m = 3.5f;
  BevDynObj perc_objects[kMaxDynObj];
  int n_obj = 0;
  int cipv_id = 0;
  float lead_dist_m = 0;
  float cipo_x_m = 0;
  float cipo_y_m = 0;
};

bool dash_lit_m(float s_m, float scroll_m = 0.0f);
Rgb color_for_obj_id(int obj_id);
Rgb traj_color_for_v(float v, float v_hi = 12.0f);
float see_opening_m(float host_vr_m, const LiveBevState& st);
float driving_see_m(const LiveBevState& st, float host_vr_m);
void advance_odom(LiveBevState& st, std::uint64_t t_ns, float speed_mps);

// Portrait 400×800 PNG. 1:1 with gf_gmt.bev_compose.render_ego_bev_png.
std::string render_ego_bev_png(const LiveBevState& st, int width = kBevW, int height = kBevH);

}  // namespace gf_foxglove
