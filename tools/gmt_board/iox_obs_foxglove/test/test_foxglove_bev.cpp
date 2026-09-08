#include "gf_foxglove/bev_compose.hpp"
#include "gf_foxglove/bev_ingest.hpp"
#include "gf_foxglove/png.hpp"
#include "gf_foxglove/ws_hub.hpp"

#if __has_include("gf_gen/types/perception_message__out__st.hpp")
#include "gf_gen/types/perception_message__out__st.hpp"
#define GF_TEST_HAS_PERC 1
#elif __has_include("gf_gen/types/perception_message_out_st.hpp")
#include "gf_gen/types/perception_message_out_st.hpp"
#define GF_TEST_HAS_PERC 1
#endif

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>

static int fails = 0;

#define CHECK(cond)                                                                 \
  do {                                                                              \
    if (!(cond)) {                                                                  \
      std::fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);          \
      ++fails;                                                                      \
    }                                                                               \
  } while (0)

int main() {
  CHECK(gf_foxglove::dash_lit_m(0.0f, 0.0f));
  CHECK(gf_foxglove::dash_lit_m(5.9f, 0.0f));
  CHECK(!gf_foxglove::dash_lit_m(6.1f, 0.0f));
  CHECK(!gf_foxglove::dash_lit_m(14.9f, 0.0f));
  CHECK(gf_foxglove::dash_lit_m(15.0f, 0.0f));
  // world-fixed scroll: (s+odom)%15
  CHECK(gf_foxglove::dash_lit_m(0.0f, 15.0f));

  const auto stop_c = gf_foxglove::traj_color_for_v(0.0f);
  const auto cruise_c = gf_foxglove::traj_color_for_v(12.0f);
  CHECK(stop_c.r > cruise_c.r);
  CHECK(cruise_c.g > stop_c.g);

  gf_foxglove::LiveBevState st;
  st.traj_x[0] = 0;
  st.traj_x[1] = 10;
  st.traj_x[2] = 20;
  st.traj_y[0] = st.traj_y[1] = st.traj_y[2] = 0;
  st.traj_v[0] = st.traj_v[1] = st.traj_v[2] = 12;
  st.n_traj = 3;
  st.n_traj_v = 3;
  st.traj_d_see_m = 80;
  st.traj_v_plan_mps = 12;
  st.host_lanes[0] = {1, 1.75f, 0, 0, 0, 0, 120, 1};
  st.host_lanes[1] = {2, -1.75f, 0, 0, 0, 0, 120, 1};
  st.n_host = 2;
  const std::string png = gf_foxglove::render_ego_bev_png(st);
  CHECK(png.size() > 8);
  CHECK(static_cast<unsigned char>(png[0]) == 0x89);
  CHECK(png.compare(1, 3, "PNG") == 0);

  gf_foxglove::LiveBevState lim = st;
  lim.v_sign_max_mps = 50.0f / 3.6f;
  lim.v_sign_min_mps = 30.0f / 3.6f;
  lim.traj_s_stop_m = 32.0f;
  lim.light_sign_name = 196;
  lim.lon_accel_mps2 = -1.2f;
  const std::string png_lim = gf_foxglove::render_ego_bev_png(lim);
  CHECK(png_lim.size() > 8);
  CHECK(png != png_lim);

  // Driving see prefers Trajectory D_see when set.
  CHECK(std::fabs(gf_foxglove::driving_see_m(st, 120.0f) - 80.0f) < 0.1f);

  gf_foxglove::LiveBevState stop = st;
  stop.traj_v[0] = stop.traj_v[1] = stop.traj_v[2] = 0;
  stop.traj_d_see_m = 20;
  stop.traj_v_plan_mps = 0;
  const std::string png_stop = gf_foxglove::render_ego_bev_png(stop);
  CHECK(png != png_stop);

  CHECK(gf_foxglove::is_image_topic("/gf/driving/bev/compressed"));
  CHECK(gf_foxglove::is_image_topic("/gf/driving/camera/front/compressed"));
  CHECK(!gf_foxglove::is_image_topic("/gf/EgoMotion"));

  const std::string ego = gf_foxglove::channel_desc_json(1, "/gf/EgoMotion");
  const std::string bev = gf_foxglove::channel_desc_json(2, "/gf/driving/bev/compressed");
  // schema must be a JSON string, not a nested object
  CHECK(ego.find("\"schema\":\"{") != std::string::npos);
  CHECK(bev.find("\"schema\":\"{") != std::string::npos);
  CHECK(ego.find("schemaEncoding\":\"jsonschema\"") != std::string::npos);

  const auto img = gf_foxglove::compressed_image_json(1'500'000'000ull, png, "front");
  CHECK(img.find("\"format\":\"png\"") != std::string::npos);
  CHECK(img.find("\"sec\":1") != std::string::npos);

#if GF_TEST_HAS_PERC
  {
    gf_gen::Perception_MESSAGE_Out_St perc{};
    perc.Perception_LH_Out.m_hostline_num = 2;
    perc.Perception_LH_Out.m_LH_Estimated_Width = 3.5f;
    auto fill_h = [](gf_gen::HostLine_St& line, std::uint8_t side, float c0) {
      line.m_LH_Side = side;
      line.m_LH_Confidence = 0.95f;
      line.m_LH_Availability_State = 2;
      line.m_LH_Lanemark_Type = 1;
      line.m_LH_First_VR_Start = 0;
      line.m_LH_First_VR_End = 120;
      line.m_LH_Line_First_C0 = c0;
    };
    fill_h(perc.Perception_LH_Out.m_hostline[0], 1, 1.75f);
    fill_h(perc.Perception_LH_Out.m_hostline[1], 2, -1.75f);
    gf_foxglove::LiveBevState ingested;
    gf_foxglove::apply_sample(ingested, "Perception_MESSAGE_Out_St", &perc);
    CHECK(ingested.n_host == 2);
    gf_foxglove::LiveBevState blank;
    CHECK(gf_foxglove::render_ego_bev_png(ingested) != gf_foxglove::render_ego_bev_png(blank));
  }
#else
  std::fprintf(stderr, "FAIL: Perception type header not found — BEV ingest disabled\n");
  ++fails;
#endif

  if (fails) {
    std::fprintf(stderr, "%d check(s) failed\n", fails);
    return 1;
  }
  std::printf("gf_foxglove_bev_smoke OK\n");
  return 0;
}
