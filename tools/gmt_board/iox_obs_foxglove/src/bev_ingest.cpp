#include "gf_foxglove/bev_ingest.hpp"

#include <algorithm>
#include <cstring>

#if __has_include("gf_gen/types/ego_motion.hpp")
#include "gf_gen/types/ego_motion.hpp"
#define GF_HAS_EGO 1
#endif
#if __has_include("gf_gen/types/trajectory.hpp")
#include "gf_gen/types/trajectory.hpp"
#define GF_HAS_TRAJ 1
#endif
#if __has_include("gf_gen/types/uss_zones.hpp")
#include "gf_gen/types/uss_zones.hpp"
#define GF_HAS_USS 1
#endif
// Codegen _snake("Perception_MESSAGE_Out_St") → perception_message__out__st.hpp
// (double underscore). The single-underscore name does not exist → GF_HAS_PERC
// stayed off and BEV never ingested host lanes.
#if __has_include("gf_gen/types/perception_message__out__st.hpp")
#include "gf_gen/types/perception_message__out__st.hpp"
#define GF_HAS_PERC 1
#elif __has_include("gf_gen/types/perception_message_out_st.hpp")
#include "gf_gen/types/perception_message_out_st.hpp"
#define GF_HAS_PERC 1
#endif

namespace gf_foxglove {
namespace {

bool lane_ok(float conf, int avail, bool has_avail) {
  if (!has_avail) avail = conf >= 0.15f ? 2 : 0;
  return avail != 0 && conf >= 0.15f;
}

}  // namespace

void apply_sample(LiveBevState& st, const char* short_name, const void* sample) {
  if (!short_name || !sample) return;
#ifdef GF_HAS_EGO
  if (std::strcmp(short_name, "EgoMotion") == 0) {
    const auto& s = *static_cast<const gf_gen::EgoMotion*>(sample);
    st.speed_mps = s.speed_mps;
    st.yaw_rate_degps = s.yaw_rate_degps;
    st.steer_angle_deg = s.steer_angle_deg;
    st.gear = static_cast<int>(s.gear);
    if (s.timestamp_ns) st.t_ns = s.timestamp_ns;
    advance_odom(st, st.t_ns, st.speed_mps);
    return;
  }
#endif
#ifdef GF_HAS_TRAJ
  if (std::strcmp(short_name, "Trajectory") == 0) {
    const auto& s = *static_cast<const gf_gen::Trajectory*>(sample);
    int n = static_cast<int>(s.point_count);
    n = std::max(0, std::min(n, kMaxTrajPts));
    st.n_traj = n;
    st.n_traj_v = n;
    for (int i = 0; i < n; ++i) {
      st.traj_x[i] = s.points_x_m[i];
      st.traj_y[i] = s.points_y_m[i];
      st.traj_v[i] = s.points_v_mps[i];
    }
    st.throttle_cmd = s.throttle;
    st.brake_cmd = s.brake;
    st.traj_v_plan_mps = s.target_speed_mps;
    st.traj_d_see_m = s.D_see_m;
    st.traj_s_stop_m = s.s_stop_m;
    st.v_sign_max_mps = s.v_sign_max_mps;
    st.v_sign_min_mps = s.v_sign_min_mps;
    // Prefer Trajectory CIPV long when set (semantic), not Obj[0].
    if (s.cipv_long_m > 0.5f) {
      st.has_perc_lead = true;
      st.lead_dist_m = s.cipv_long_m;
      st.cipo_x_m = s.cipv_long_m;
    }
    if (s.timestamp_ns) st.t_ns = s.timestamp_ns;
    return;
  }
#endif
#ifdef GF_HAS_USS
  if (std::strcmp(short_name, "UssZones") == 0) {
    const auto& s = *static_cast<const gf_gen::UssZones*>(sample);
    st.nearest_cm = static_cast<float>(s.nearest_cm);
    return;
  }
#endif
#ifdef GF_HAS_PERC
  if (std::strcmp(short_name, "Perception_MESSAGE_Out_St") == 0) {
    const auto& s = *static_cast<const gf_gen::Perception_MESSAGE_Out_St*>(sample);
    const auto& lh = s.Perception_LH_Out;
    st.n_host = 0;
    const int nh = std::min(static_cast<int>(lh.m_hostline_num), kMaxHostLanes);
    for (int i = 0; i < nh; ++i) {
      const auto& it = lh.m_hostline[i];
      const float conf = static_cast<float>(it.m_LH_Confidence);
      const int avail = static_cast<int>(it.m_LH_Availability_State);
      if (!lane_ok(conf, avail, true)) continue;
      const float x0 = it.m_LH_First_VR_Start;
      float x1 = it.m_LH_First_VR_End;
      if (x1 <= x0 + 0.25f) continue;
      x1 = std::min(x1, kDBevM);
      HostLanePoly p;
      p.side = static_cast<int>(it.m_LH_Side);
      p.c0 = it.m_LH_Line_First_C0;
      p.c1 = it.m_LH_Line_First_C1;
      p.c2 = it.m_LH_Line_First_C2;
      p.c3 = it.m_LH_Line_First_C3;
      p.x0 = x0;
      p.x1 = x1;
      p.lanemark_type = static_cast<int>(it.m_LH_Lanemark_Type);
      st.host_lanes[st.n_host++] = p;
    }
    st.has_perc_lanes = st.n_host >= 1;
    if (lh.m_LH_Estimated_Width > 0.5f) st.lane_width_m = lh.m_LH_Estimated_Width;

    const auto& la = s.Perception_LA_Out;
    st.n_adj = 0;
    const int na = std::min(static_cast<int>(la.m_adj_line_num), kMaxAdjLanes);
    for (int i = 0; i < na; ++i) {
      const auto& it = la.m_adj_line[i];
      const float conf = static_cast<float>(it.m_LA_Confidence);
      const int avail = static_cast<int>(it.m_LA_Availability_State);
      if (!lane_ok(conf, avail, true)) continue;
      const float x0 = it.m_LA_View_Range_Start;
      float x1 = it.m_LA_View_Range_End;
      if (x1 <= x0 + 0.25f) continue;
      x1 = std::min(x1, kDBevM);
      AdjLanePoly p;
      p.side = static_cast<int>(it.m_LA_Line_Side);
      p.c0 = it.m_LA_Line_C0;
      p.c1 = it.m_LA_Line_C1;
      p.c2 = it.m_LA_Line_C2;
      p.c3 = it.m_LA_Line_C3;
      p.x0 = x0;
      p.x1 = x1;
      p.lanemark_type = static_cast<int>(it.m_LA_Lanemark_Type);
      st.adj_lanes[st.n_adj++] = p;
    }

    const auto& dyn = s.Perception_DYN_OBJ_Out;
    const int vd = std::min(static_cast<int>(dyn.m_OBJ_VD_Count), kMaxDynObj);
    const int cipv = static_cast<int>(dyn.m_OBJ_VD_CIPV_ID);
    st.cipv_id = cipv;
    st.n_obj = 0;
    for (int i = 0; i < vd; ++i) {
      const auto& it = dyn.m_Obj_item[i];
      const int oid = static_cast<int>(it.m_OBJ_ID);
      const float dist = it.m_OBJ_Long_Distance;
      if (oid <= 0 || dist <= 0.5f || dist > kDBevM) continue;
      BevDynObj o;
      o.obj_id = oid;
      o.x_m = dist;
      o.y_m = it.m_OBJ_Lat_Distance;
      o.is_cipv = (cipv != 0 && oid == cipv);
      o.obj_class = static_cast<int>(it.m_OBJ_Object_Class);
      o.length_m = it.m_OBJ_Length > 0.5f ? it.m_OBJ_Length : 4.5f;
      o.width_m = it.m_OBJ_Width > 0.5f ? it.m_OBJ_Width : 1.8f;
      o.heading_rad = it.m_OBJ_Heading;
      st.perc_objects[st.n_obj++] = o;
    }
    // ME: CIPV only by ID. Never promote Obj[0].
    st.has_perc_lead = false;
    st.lead_dist_m = 0;
    st.cipo_x_m = 0;
    st.cipo_y_m = 0;
    if (cipv != 0) {
      for (int i = 0; i < st.n_obj; ++i) {
        if (st.perc_objects[i].is_cipv) {
          st.has_perc_lead = true;
          st.lead_dist_m = st.perc_objects[i].x_m;
          st.cipo_x_m = st.perc_objects[i].x_m;
          st.cipo_y_m = st.perc_objects[i].y_m;
          break;
        }
      }
    }

    // Prefer Relevant stop (196/164) over green (198) for HUD.
    const auto& tsr = s.Perception_DSTSR_Out;
    const int n_tsr = std::min(6, static_cast<int>(tsr.m_tsr_num));
    float best_d = 1.0e9f;
    int best_name = 0;
    int best_rank = 9;
    for (int i = 0; i < n_tsr; ++i) {
      const auto& it = tsr.m_TSR_Item[i];
      const int name = static_cast<int>(it.m_DSTSR_Sign_Name);
      if (name != 164 && name != 196 && name != 198) continue;
      if (static_cast<int>(it.m_DSTSR_Relevancy) != 0) continue;
      const float d = it.m_DSTSR_Sign_Long_Distance;
      if (d < -8.0f || d > kDBevM) continue;
      const int rank = (name == 198) ? 1 : 0;
      if (rank > best_rank) continue;
      if (rank == best_rank && d >= best_d) continue;
      best_d = d;
      best_name = name;
      best_rank = rank;
    }
    st.light_sign_name = best_name;
    return;
  }
#endif
}

}  // namespace gf_foxglove
