#include "gf_foxglove/bev_ndjson.hpp"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

int main() {
  gf_foxglove::LiveBevState st;
  const char* ego =
      R"({"topic":"/gf/EgoMotion","t_ns":1000,"data":{"timestamp_ns":1000,"speed_mps":8.5,"yaw_rate_degps":0,"steer_angle_deg":1.2,"gear":3}})";
  if (!gf_foxglove::apply_ndjson_row(st, ego) || st.speed_mps < 8.0f) {
    std::fprintf(stderr, "ego apply failed speed=%g\n", static_cast<double>(st.speed_mps));
    return 1;
  }
  const char* traj =
      R"({"topic":"/gf/Trajectory","data":{"points_x_m":[0,10,20],"points_y_m":[0,0.1,-0.1],"points_v_mps":[8,8,7],"throttle":0.2,"brake":0,"D_see_m":40,"s_stop_m":120}})";
  if (!gf_foxglove::apply_ndjson_row(st, traj) || st.n_traj != 3) {
    std::fprintf(stderr, "traj apply failed n=%d\n", st.n_traj);
    return 2;
  }
  const char* perc =
      R"({"topic":"/gf/Perception_MESSAGE_Out_St","data":{"Perception_LH_Out":{"m_hostline_num":2,"m_LH_Estimated_Width":3.5,"m_hostline":[{"m_LH_Side":1,"m_LH_Confidence":0.9,"m_LH_Availability_State":2,"m_LH_Lanemark_Type":1,"m_LH_First_VR_Start":0,"m_LH_First_VR_End":80,"m_LH_Line_First_C0":1.75,"m_LH_Line_First_C1":0,"m_LH_Line_First_C2":0,"m_LH_Line_First_C3":0},{"m_LH_Side":2,"m_LH_Confidence":0.9,"m_LH_Availability_State":2,"m_LH_Lanemark_Type":1,"m_LH_First_VR_Start":0,"m_LH_First_VR_End":80,"m_LH_Line_First_C0":-1.75,"m_LH_Line_First_C1":0,"m_LH_Line_First_C2":0,"m_LH_Line_First_C3":0}]},"Perception_LA_Out":{"m_adj_line_num":0,"m_adj_line":[]},"Perception_DYN_OBJ_Out":{"m_OBJ_VD_Count":1,"m_OBJ_Ped_Count":0,"m_OBJ_VD_CIPV_ID":7,"m_Obj_item":[{"m_OBJ_ID":7,"m_OBJ_Object_Class":1,"m_OBJ_Long_Distance":25,"m_OBJ_Lat_Distance":0.1,"m_OBJ_Heading":0,"m_OBJ_Length":4.5,"m_OBJ_Width":1.8}]}}})";
  if (!gf_foxglove::apply_ndjson_row(st, perc) || st.n_host < 2 || !st.has_perc_lead) {
    std::fprintf(stderr, "perc apply failed host=%d lead=%d\n", st.n_host,
                 static_cast<int>(st.has_perc_lead));
    return 3;
  }
  const auto png = gf_foxglove::render_ego_bev_png(st);
  if (png.size() < 8 || png[0] != '\x89') {
    std::fprintf(stderr, "png render failed size=%zu\n", png.size());
    return 4;
  }
  std::fprintf(stderr, "gf_foxglove_ndjson_smoke ok png=%zu\n", png.size());
  return 0;
}
