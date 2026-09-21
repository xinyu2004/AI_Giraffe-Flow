#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_ara/com/binding/iceoryx/wait_set.hpp"
#include "gf_ara/collector/event_collector.hpp"
#include "gf_ara/runtime/process_bringup.hpp"
#include "gf_gen/proxy/ego_motion_proxy.hpp"
#include "gf_gen/proxy/perception_message__out__st_proxy.hpp"
#include "gf_gen/proxy/perception__rear__out__st_proxy.hpp"
#include "gf_gen/proxy/freespace_near_proxy.hpp"
#include "gf_gen/proxy/surround_world_proxy.hpp"
#include "gf_gen/skeleton/trajectory_skeleton.hpp"
#include "gf_gen/skeleton/freespace_skeleton.hpp"

#include "gf_app/frame_watch.hpp"

#include "m_plan_tick.hpp"
#include "fuse_driving_fs.hpp"
#include "fs_envelope/fs_mounts.hpp"

#include "gf_octave_planning/plan_cal.hpp"
#include "gf_ara/log/logger.hpp"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <optional>
#include <sstream>
#include <string>

namespace {

constexpr const char* kProcess = "planning.driving_plus";
constexpr int kDynCap = 13;
constexpr float kObjDMaxM = 130.0f;
/** LC health window (steady_clock); tighter than surround/RCM 500ms silence. */
constexpr std::uint64_t kLcStaleNs = 200000000ULL;
/** Supervisor slice only — not an on_change publish clock. */
constexpr std::uint32_t kWaitSliceMs = 10;
constexpr std::uint64_t kIdEgo = 1;
constexpr std::uint64_t kIdPerc = 2;
constexpr std::uint64_t kIdSurround = 3;
constexpr std::uint64_t kIdRcm = 4;
constexpr std::uint64_t kIdNear = 5;

/** Rising-edge LC health fault → Collector/PER (source=process). */
void ReportLcFaultEdge(bool bad_now, bool* was_bad, const char* event_id) {
  if (!was_bad || !event_id || !event_id[0]) {
    return;
  }
  if (bad_now && !*was_bad) {
    gf_ara::collector::EventCollector::Instance().ReportEvent(
        "process", event_id, "process=planning.driving_plus",
        gf_ara::collector::EventSeverity::kError);
  }
  *was_bad = bad_now;
}

struct HostLaneGeom {
  bool valid{false};
  float c0{0.0f};
  float c1{0.0f};
  float c2{0.0f};
  float c3{0.0f};
  float x_end{0.0f};
  float width_m{3.5f};
  float e_y{0.0f};
  float conf{1.0f};
  float lane_count{1.0f};

  float y_at(float x) const {
    return c0 + c1 * x + c2 * x * x + c3 * x * x * x;
  }
};

struct PercView {
  HostLaneGeom lane{};
  oct_gen::PlanObj obj[oct_gen::kObjNMax]{};
  std::uint8_t obj_assign[oct_gen::kObjNMax]{};
  std::uint16_t obj_id[oct_gen::kObjNMax]{};
  int nobj{0};
  int dyn_raw{0};
  int lh_n{0};
  // Road corridor for FS clip: prefer LRE, else LH (+ LA outers).
  gf_plan_fs::RoadEdgePoly road_left{};
  gf_plan_fs::RoadEdgePoly road_right{};
  // Extra no-cross walls (solid yellow / solid marks) when LRE thin or missing.
  gf_plan_fs::RoadEdgePoly hard_walls[6]{};
  int n_hard_walls{0};
  // Host / adj bands for per-lane clear (LH + LA; not LRE).
  gf_plan_fs::LaneBands lane_bands{};
  // Live / process curves — semantic, not slot index.
  float cipv_long_m{0.0f};
  float cipv_rel_v{0.0f};
  // Relevant DSTSR e_std_* (mps). 0 = none. Not plan_v_cap_vis.
  float v_sign_max_mps{0.0f};
  float v_sign_min_mps{0.0f};
};

HostLaneGeom HostLaneFromPerc(const gf_gen::Perception_MESSAGE_Out_St& perc) {
  HostLaneGeom g{};
  const auto& lh = perc.Perception_LH_Out;
  if (lh.m_hostline_num < 1) {
    return g;
  }
  bool have_l = false;
  bool have_r = false;
  float lc0 = 0.0f, lc1 = 0.0f, lc2 = 0.0f, lc3 = 0.0f, lx1 = 0.0f;
  float rc0 = 0.0f, rc1 = 0.0f, rc2 = 0.0f, rc3 = 0.0f, rx1 = 0.0f;
  float conf = 0.0f;
  const std::uint8_t n = std::min<std::uint8_t>(lh.m_hostline_num, 4);
  for (std::uint8_t i = 0; i < n; ++i) {
    const auto& line = lh.m_hostline[i];
    if (line.m_LH_Confidence < 0.1f && line.m_LH_Availability_State == 0) {
      continue;
    }
    // Published VR only — do not invent 60 m.
    const float x1 = line.m_LH_First_VR_End;
    if (x1 <= 0.5f) {
      continue;
    }
    conf = std::max(conf, line.m_LH_Confidence);
    if (line.m_LH_Side == 1) {
      have_l = true;
      lc0 = line.m_LH_Line_First_C0;
      lc1 = line.m_LH_Line_First_C1;
      lc2 = line.m_LH_Line_First_C2;
      lc3 = line.m_LH_Line_First_C3;
      lx1 = x1;
    } else if (line.m_LH_Side == 2) {
      have_r = true;
      rc0 = line.m_LH_Line_First_C0;
      rc1 = line.m_LH_Line_First_C1;
      rc2 = line.m_LH_Line_First_C2;
      rc3 = line.m_LH_Line_First_C3;
      rx1 = x1;
    }
  }
  if (have_l && have_r) {
    if (gf_octave_planning::plan_host_pair_ok(lc0, rc0)) {
      g.valid = true;
      g.c0 = 0.5f * (lc0 + rc0);
      g.c1 = 0.5f * (lc1 + rc1);
      g.c2 = 0.5f * (lc2 + rc2);
      g.c3 = 0.5f * (lc3 + rc3);
      g.x_end = std::min(lx1, rx1);
      g.width_m = std::max(2.5f, std::fabs(lc0 - rc0));
    }
  } else if (have_l || have_r) {
    const float half = 1.75f;
    float use_l = lc0;
    float use_r = rc0;
    if (have_l) {
      use_r = lc0 - 2.0f * half;
    } else {
      use_l = rc0 + 2.0f * half;
    }
    if (gf_octave_planning::plan_host_pair_ok(use_l, use_r)) {
      g.valid = true;
      g.c0 = 0.5f * (use_l + use_r);
      if (have_l) {
        g.c1 = lc1;
        g.c2 = lc2;
        g.c3 = lc3;
        g.x_end = lx1;
      } else {
        g.c1 = rc1;
        g.c2 = rc2;
        g.c3 = rc3;
        g.x_end = rx1;
      }
      g.width_m = 3.5f;
    }
  }
  if (lh.m_LH_Estimated_Width > 0.5f) {
    g.width_m = lh.m_LH_Estimated_Width;
  }
  g.e_y = g.y_at(0.0f);
  g.conf = g.valid ? std::max(conf, 0.20f) : 0.0f;
  // Host lane_count = driving lanes. FCM has no that field: 1 + adj present.
  g.lane_count = 1.0f;
  if (g.valid && perc.Perception_LA_Out.m_adj_line_num >= 1) {
    g.lane_count = 2.0f;
  }
  return g;
}

/** Corridor for FS clip: LRE preferred, else LH (+ LA outers). Solid marks → hard walls. */
void FillRoadCorridor(const gf_gen::Perception_MESSAGE_Out_St& perc, PercView& v) {
  auto push_hard = [&](gf_plan_fs::RoadEdgePoly p) {
    if (!p.valid || !p.hard || v.n_hard_walls >= 6) {
      return;
    }
    v.hard_walls[v.n_hard_walls++] = p;
  };
  auto edge = [](float c0, float c1, float c2, float c3, float vr, bool hard) {
    gf_plan_fs::RoadEdgePoly p;
    p.valid = true;
    p.hard = hard;
    p.c0 = c0;
    p.c1 = c1;
    p.c2 = c2;
    p.c3 = c3;
    p.vr_m = vr;
    return p;
  };

  const auto& lre = perc.Perception_LRE_Out;
  const bool have_lre =
      lre.m_roadedge_num >= 1 && lre.m_roadedge_line[0].m_LRE_Availability_State != 0;
  for (std::uint8_t i = 0; i < std::min<std::uint8_t>(lre.m_roadedge_num, 2); ++i) {
    const auto& e = lre.m_roadedge_line[i];
    if (e.m_LRE_Availability_State == 0 || e.m_LRE_View_Range_End < 0.5f) {
      continue;
    }
    auto p = edge(e.m_LRE_Line_C0, e.m_LRE_Line_C1, e.m_LRE_Line_C2, e.m_LRE_Line_C3,
                  e.m_LRE_View_Range_End, true);
    if (e.m_LRE_Side == 1) {
      v.road_left = p;
    } else if (e.m_LRE_Side == 2) {
      v.road_right = p;
    }
  }

  const auto& lh = perc.Perception_LH_Out;
  for (std::uint8_t i = 0; i < std::min<std::uint8_t>(lh.m_hostline_num, 4); ++i) {
    const auto& line = lh.m_hostline[i];
    if (line.m_LH_Availability_State == 0 || line.m_LH_First_VR_End < 0.5f) {
      continue;
    }
    const bool solid = (static_cast<int>(line.m_LH_Lanemark_Type) == 1) ||
                       (static_cast<int>(line.m_LH_DLM_Type) == 3);
    auto p = edge(line.m_LH_Line_First_C0, line.m_LH_Line_First_C1, line.m_LH_Line_First_C2,
                  line.m_LH_Line_First_C3, line.m_LH_First_VR_End, solid);
    if (line.m_LH_Side == 1 && !v.road_left.valid) {
      v.road_left = p;
    } else if (line.m_LH_Side == 2 && !v.road_right.valid) {
      v.road_right = p;
    }
    if (solid) {
      push_hard(p);
    }
  }

  const auto& la = perc.Perception_LA_Out;
  for (std::uint8_t i = 0; i < std::min<std::uint8_t>(la.m_adj_line_num, 4); ++i) {
    const auto& line = la.m_adj_line[i];
    if (line.m_LA_Availability_State == 0 || line.m_LA_View_Range_End < 0.5f) {
      continue;
    }
    const std::uint8_t side = line.m_LA_Line_Side;
    const bool solid = (static_cast<int>(line.m_LA_Lanemark_Type) == 1);
    auto p = edge(line.m_LA_Line_C0, line.m_LA_Line_C1, line.m_LA_Line_C2, line.m_LA_Line_C3,
                  line.m_LA_View_Range_End, solid);
    if (!have_lre) {
      if ((side == 1 || side == 6) && v.road_left.valid && p.c0 > v.road_left.c0) {
        v.road_left = p;
      }
      if ((side == 4 || side == 5) && v.road_right.valid && p.c0 < v.road_right.c0) {
        v.road_right = p;
      }
    }
    if (solid) {
      push_hard(p);
    }
  }
}

/** Host LH + LA adj bands for per-lane clear (geometry ownership). */
void FillLaneBands(const gf_gen::Perception_MESSAGE_Out_St& perc, PercView& v) {
  auto edge = [](float c0, float c1, float c2, float c3, float vr) {
    gf_plan_fs::RoadEdgePoly p;
    p.valid = true;
    p.hard = false;
    p.c0 = c0;
    p.c1 = c1;
    p.c2 = c2;
    p.c3 = c3;
    p.vr_m = vr;
    return p;
  };
  const auto& lh = perc.Perception_LH_Out;
  for (std::uint8_t i = 0; i < std::min<std::uint8_t>(lh.m_hostline_num, 4); ++i) {
    const auto& line = lh.m_hostline[i];
    if (line.m_LH_Availability_State == 0 || line.m_LH_First_VR_End < 0.5f) {
      continue;
    }
    auto p = edge(line.m_LH_Line_First_C0, line.m_LH_Line_First_C1, line.m_LH_Line_First_C2,
                  line.m_LH_Line_First_C3, line.m_LH_First_VR_End);
    if (line.m_LH_Side == 1) {
      v.lane_bands.host_l = p;
    } else if (line.m_LH_Side == 2) {
      v.lane_bands.host_r = p;
    }
  }
  // Single-side LH: synthesize opposite at ±half width.
  if (v.lane_bands.host_l.valid != v.lane_bands.host_r.valid) {
    const float half = (v.lane.width_m > 2.0f) ? (0.5f * v.lane.width_m) : 1.75f;
    if (v.lane_bands.host_l.valid && !v.lane_bands.host_r.valid) {
      v.lane_bands.host_r = v.lane_bands.host_l;
      v.lane_bands.host_r.c0 = v.lane_bands.host_l.c0 - 2.0f * half;
    } else if (v.lane_bands.host_r.valid && !v.lane_bands.host_l.valid) {
      v.lane_bands.host_l = v.lane_bands.host_r;
      v.lane_bands.host_l.c0 = v.lane_bands.host_r.c0 + 2.0f * half;
    }
  }
  const auto& la = perc.Perception_LA_Out;
  for (std::uint8_t i = 0; i < std::min<std::uint8_t>(la.m_adj_line_num, 4); ++i) {
    const auto& line = la.m_adj_line[i];
    if (line.m_LA_Availability_State == 0 || line.m_LA_View_Range_End < 0.5f) {
      continue;
    }
    const std::uint8_t side = line.m_LA_Line_Side;
    auto p = edge(line.m_LA_Line_C0, line.m_LA_Line_C1, line.m_LA_Line_C2, line.m_LA_Line_C3,
                  line.m_LA_View_Range_End);
    if (side == 1 || side == 6) {
      if (!v.lane_bands.left_outer.valid || p.c0 > v.lane_bands.left_outer.c0) {
        v.lane_bands.left_outer = p;
      }
    } else if (side == 4 || side == 5) {
      if (!v.lane_bands.right_outer.valid || p.c0 < v.lane_bands.right_outer.c0) {
        v.lane_bands.right_outer = p;
      }
    }
  }
  v.lane_bands.have_left =
      v.lane_bands.left_outer.valid && v.lane_bands.host_l.valid;
  v.lane_bands.have_right =
      v.lane_bands.right_outer.valid && v.lane_bands.host_r.valid;
}

bool ObjAlreadyPacked(const oct_gen::PlanObj* obj, int n, float d, float lat) {
  for (int i = 0; i < n; ++i) {
    if (std::fabs(obj[i].d - d) < 1.5f && std::fabs(obj[i].lat - lat) < 0.8f) {
      return true;
    }
  }
  return false;
}

bool OccAlreadyPacked(const gf_plan_fs::FsOccSample* occ, int n, float x, float y) {
  for (int i = 0; i < n; ++i) {
    if (std::fabs(occ[i].x_m - x) < 3.0f && std::fabs(occ[i].y_m - y) < 1.5f) {
      return true;
    }
  }
  return false;
}

/** Occupy-only (RCM / Surround): side/rear NearObst. Does NOT feed forward lane clear. */
void PushFsOcc(gf_plan_fs::FsOccSample* occ, int* n_occ, int cap, float x, float y,
               std::uint8_t cls, float half_l_m, float half_w_m) {
  if (!occ || !n_occ || *n_occ >= cap) {
    return;
  }
  if (std::fabs(x) < 0.3f) {
    return;
  }
  if (OccAlreadyPacked(occ, *n_occ, x, y)) {
    return;
  }
  const bool hard = gf_plan_fs::IsHardStaticCls(cls);
  const float hw = half_w_m > 0.2f ? half_w_m : (hard ? 0.45f : 0.95f);
  const float hl = half_l_m > 0.2f ? half_l_m : (hard ? 0.3f : 1.8f);
  occ[*n_occ].x_m = x;
  occ[*n_occ].y_m = y;
  occ[*n_occ].hard_world = hard;
  occ[*n_occ].half_w_m = hw;
  occ[*n_occ].half_l_m = hl;
  ++(*n_occ);
}

/** FCM: occupy + forward lane clear (host/left/right). */
void PushFsOccClear(gf_plan_fs::FsOccSample* occ, int* n_occ, gf_plan_fs::LaneClearSample* clear,
                    int* n_clear, int cap, float x, float y, std::uint8_t cls, std::uint16_t id,
                    std::uint8_t assign, float half_l_m, float half_w_m) {
  if (!occ || !n_occ || !clear || !n_clear || *n_occ >= cap) {
    return;
  }
  if (std::fabs(x) < 0.3f) {
    return;
  }
  if (OccAlreadyPacked(occ, *n_occ, x, y)) {
    return;
  }
  const bool hard = gf_plan_fs::IsHardStaticCls(cls);
  const float hw = half_w_m > 0.2f ? half_w_m : (hard ? 0.45f : 0.95f);
  const float hl = half_l_m > 0.2f ? half_l_m : (hard ? 0.3f : 2.25f);
  occ[*n_occ].x_m = x;
  occ[*n_occ].y_m = y;
  occ[*n_occ].hard_world = hard;
  occ[*n_occ].half_w_m = hw;
  occ[*n_occ].half_l_m = hl;
  ++(*n_occ);
  if (*n_clear < cap) {
    clear[*n_clear].x_m = x;
    clear[*n_clear].y_m = y;
    clear[*n_clear].half_l_m = hl;
    clear[*n_clear].half_w_m = hw;
    clear[*n_clear].assign = assign;
    clear[*n_clear].cls = cls;
    clear[*n_clear].id = id;
    clear[*n_clear].hard_world = hard;
    ++(*n_clear);
  }
}

template <typename ObjT>
void TryPushObj(PercView& v, const ObjT& o) {
  if (v.nobj >= oct_gen::kObjNMax) {
    return;
  }
  // Allow rear (x<0) for FS occupy; skip only absurd range.
  if (o.m_OBJ_ID == 0 || o.m_OBJ_Long_Distance < -kObjDMaxM ||
      o.m_OBJ_Long_Distance > kObjDMaxM) {
    return;
  }
  if (std::fabs(o.m_OBJ_Long_Distance) < 0.3f) {
    return;
  }
  const float d = o.m_OBJ_Long_Distance;
  const float lat = o.m_OBJ_Lat_Distance;
  if (ObjAlreadyPacked(v.obj, v.nobj, d, lat)) {
    return;
  }
  oct_gen::PlanObj row{};
  row.d = d;
  row.rel = o.m_OBJ_Relative_Long_Velocity;
  row.lat = lat;
  row.len_m = std::max(o.m_OBJ_Length, 0.5f);
  row.cls = static_cast<float>(o.m_OBJ_Object_Class);
  row.heading = o.m_OBJ_Heading;  // radians, same as Host heading_rad
  row.is_ped = (static_cast<int>(o.m_OBJ_Object_Class) == 5) ? 1.0f : 0.0f;
  v.obj_assign[v.nobj] = static_cast<std::uint8_t>(o.m_OBJ_Lane_Assignment);
  v.obj_id[v.nobj] = static_cast<std::uint16_t>(o.m_OBJ_ID);
  v.obj[v.nobj++] = row;
}

// Gold e_std_* / e_lgt_* → km/h. Returns <0 if not a numeric speed Sign_Name.
float StdSignNameToKph(int name) {
  if (name >= 0 && name <= 13) {
    return static_cast<float>((name + 1) * 10);
  }
  if (name == 100) {
    return 5.0f;
  }
  if (name >= 101 && name <= 114) {
    return static_cast<float>(5 + (name - 100) * 10);
  }
  if (name == 85) {
    return 150.0f;
  }
  if (name == 86) {
    return 160.0f;
  }
  if (name >= 28 && name <= 41) {
    return static_cast<float>((name - 27) * 10);
  }
  if (name >= 115 && name <= 127) {
    return static_cast<float>(5 + (name - 115) * 10);
  }
  return -1.0f;
}

bool PreferSignCandidate(float d_new, float d_cur, bool have) {
  if (!have) {
    return true;
  }
  // Nearest ahead (d>=0); else most recently passed in behind window.
  if (d_new >= 0.0f && d_cur >= 0.0f) {
    return d_new < d_cur;
  }
  if (d_new >= 0.0f) {
    return true;
  }
  if (d_cur >= 0.0f) {
    return false;
  }
  return d_new > d_cur;
}

// One walk of dyn[] + one walk of hostlines. Empty → nobj=0 (Host _pack_obj []).
// CIPV first, then the rest. Do not LeadFromPerc then pack again.
PercView ExtractPerc(const gf_gen::Perception_MESSAGE_Out_St& perc) {
  PercView v{};
  v.lane = HostLaneFromPerc(perc);
  FillRoadCorridor(perc, v);
  FillLaneBands(perc, v);
  const auto& dyn = perc.Perception_DYN_OBJ_Out;
  v.dyn_raw = static_cast<int>(dyn.m_OBJ_VD_Count) + static_cast<int>(dyn.m_OBJ_Ped_Count);
  v.lh_n = static_cast<int>(perc.Perception_LH_Out.m_hostline_num);
  const int n_src = std::min(kDynCap, std::max(v.dyn_raw, static_cast<int>(dyn.m_OBJ_VD_Count)));
  if (dyn.m_OBJ_VD_CIPV_ID != 0) {
    for (int i = 0; i < n_src; ++i) {
      if (dyn.m_Obj_item[i].m_OBJ_ID == dyn.m_OBJ_VD_CIPV_ID) {
        TryPushObj(v, dyn.m_Obj_item[i]);
        v.cipv_long_m = dyn.m_Obj_item[i].m_OBJ_Long_Distance;
        v.cipv_rel_v = dyn.m_Obj_item[i].m_OBJ_Relative_Long_Velocity;
        break;
      }
    }
  }
  for (int i = 0; i < n_src; ++i) {
    TryPushObj(v, dyn.m_Obj_item[i]);
  }
  const auto& st = perc.Perception_STATIC_OBJ_Out;
  const int n_st = std::min(10, static_cast<int>(st.m_Static_OBJ_Count));
  for (int i = 0; i < n_st; ++i) {
    const auto& o = st.m_Obj_item[i];
    if (o.m_OBJ_ID == 0 || o.m_OBJ_Long_Distance < -kObjDMaxM ||
        o.m_OBJ_Long_Distance > kObjDMaxM) {
      continue;
    }
    if (std::fabs(o.m_OBJ_Long_Distance) < 0.3f) {
      continue;
    }
    if (ObjAlreadyPacked(v.obj, v.nobj, o.m_OBJ_Long_Distance, o.m_OBJ_Lat_Distance)) {
      continue;
    }
    if (v.nobj >= oct_gen::kObjNMax) {
      break;
    }
    oct_gen::PlanObj row{};
    row.d = o.m_OBJ_Long_Distance;
    row.rel = 0.0f;
    row.lat = o.m_OBJ_Lat_Distance;
    row.len_m = std::max(o.m_OBJ_Length, 0.5f);
    row.cls = static_cast<float>(o.m_OBJ_Object_Class);
    row.heading = o.m_OBJ_Heading;
    row.is_ped = (static_cast<int>(o.m_OBJ_Object_Class) == 5) ? 1.0f : 0.0f;
    v.obj_assign[v.nobj] = static_cast<std::uint8_t>(o.m_OBJ_Lane_Assignment);
    v.obj_id[v.nobj] = static_cast<std::uint16_t>(o.m_OBJ_ID);
    v.obj[v.nobj++] = row;
  }
  const auto& tsr = perc.Perception_DSTSR_Out;
  const int n_tsr = std::min(6, static_cast<int>(tsr.m_tsr_num));
  float max_d = 0.0f;
  float min_d = 0.0f;
  bool have_max = false;
  bool have_min = false;
  for (int i = 0; i < n_tsr; ++i) {
    const auto& it = tsr.m_TSR_Item[i];
    const int name = static_cast<int>(it.m_DSTSR_Sign_Name);
    // e_trafficSignals=164, e_stopAhead=196 → cls_reg_stop (not a car / not occupy).
    if (name == 164 || name == 196) {
      // ME: host stop only from Relevant (0); other-lane / far ignored.
      if (static_cast<int>(it.m_DSTSR_Relevancy) != 0) {
        continue;
      }
      const float d = it.m_DSTSR_Sign_Long_Distance;
      const float lat = it.m_DSTSR_Sign_Lat_Distance;
      if (d < -gf_octave_planning::plan_cal().reg_stop_behind_m || d > kObjDMaxM) {
        continue;
      }
      if (ObjAlreadyPacked(v.obj, v.nobj, d, lat) || v.nobj >= oct_gen::kObjNMax) {
        continue;
      }
      oct_gen::PlanObj row{};
      row.d = d;
      row.rel = 0.0f;
      row.lat = lat;
      row.len_m = 1.0f;
      row.cls = gf_octave_planning::plan_cal().cls_reg_stop;
      row.heading = 0.0f;
      row.is_ped = 0.0f;
      v.obj[v.nobj++] = row;
      continue;
    }
    const float kph = StdSignNameToKph(name);
    if (kph < 0.0f) {
      continue;
    }
    if (static_cast<int>(it.m_DSTSR_Relevancy) != 0) {
      continue;
    }
    const float d = it.m_DSTSR_Sign_Long_Distance;
    if (d < -gf_octave_planning::plan_cal().reg_stop_behind_m || d > kObjDMaxM) {
      continue;
    }
    const float mps = kph / 3.6f;
    const bool is_min = static_cast<int>(it.m_DSTSR_Sup1_SignName) == 27;
    if (is_min) {
      if (PreferSignCandidate(d, min_d, have_min)) {
        have_min = true;
        min_d = d;
        v.v_sign_min_mps = mps;
      }
    } else if (PreferSignCandidate(d, max_d, have_max)) {
      have_max = true;
      max_d = d;
      v.v_sign_max_mps = mps;
    }
  }
  return v;
}

std::uint8_t CtrlModeId(const char* mode) {
  if (!mode) {
    return 0;
  }
  if (std::strcmp(mode, "acc") == 0) {
    return 1;
  }
  if (std::strcmp(mode, "aeb") == 0) {
    return 2;
  }
  if (std::strcmp(mode, "pullaway") == 0) {
    return 3;
  }
  return 0;
}

std::uint64_t now_ns() {
  return static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(
          std::chrono::steady_clock::now().time_since_epoch())
          .count());
}

void ApplyTick(const oct_gen::PlanTickOut& tick, const gf_gen::EgoMotion& ego,
               const PercView& view, gf_gen::Trajectory& traj) {
  traj.point_count = static_cast<std::uint8_t>(oct_gen::kLatTrajPoints);
  traj.gear_shift_first = ego.gear;
  traj.gear_shift_second = 0;
  for (int i = 0; i < oct_gen::kLatTrajPoints; ++i) {
    traj.points_x_m[i] = tick.path.x_m[i];
    traj.points_y_m[i] = tick.path.y_m[i];
    traj.points_v_mps[i] = tick.path.v_mps[i];
  }
  traj.throttle = tick.throttle;
  traj.brake = tick.brake;
  traj.steer = tick.steer;
  traj.target_speed_mps = tick.target_speed_mps;
  traj.ctrl_mode = CtrlModeId(tick.mode);
  // ADC: no D_see_m on the wire (planning space = Freespace only; no HUD bypass).
  traj.D_see_m = 0.0f;
  traj.s_stop_m = tick.s_stop;
  traj.cipv_long_m = view.cipv_long_m;
  traj.cipv_rel_v = view.cipv_rel_v;
  traj.v_sign_max_mps = view.v_sign_max_mps;
  traj.v_sign_min_mps = view.v_sign_min_mps;
}

void ClipPathToFront(gf_gen::Trajectory& traj, float d_front) {
  const float cap = std::max(1.0f, d_front);
  int n = static_cast<int>(traj.point_count);
  while (n > 2 && traj.points_x_m[n - 1] > cap + 0.05f) {
    --n;
  }
  traj.point_count = static_cast<std::uint8_t>(n);
}

/** Path reader: stay inside host lane envelope laterally + d_front longitudinally. */
void ClipPathToLaneEnvelope(gf_gen::Trajectory& traj, float d_front,
                            const gf_plan_fs::RoadEdgePoly& host_l,
                            const gf_plan_fs::RoadEdgePoly& host_r, float margin_m = 0.25f) {
  ClipPathToFront(traj, d_front);
  if (!host_l.valid || !host_r.valid) {
    return;
  }
  int n = static_cast<int>(traj.point_count);
  int keep = n;
  for (int i = 0; i < n; ++i) {
    const float x = std::max(0.0f, traj.points_x_m[i]);
    float yl = gf_plan_fs::RoadEdgeY(host_l, x);
    float yr = gf_plan_fs::RoadEdgeY(host_r, x);
    if (yr > yl) {
      std::swap(yr, yl);
    }
    const float y = traj.points_y_m[i];
    if (y > yl - margin_m || y < yr + margin_m) {
      // Soft clamp into band (keep path continuous); hard truncate if far outside
      if (y > yl + 1.5f || y < yr - 1.5f) {
        keep = std::max(2, i);
        break;
      }
      traj.points_y_m[i] = std::min(yl - margin_m, std::max(yr + margin_m, y));
    }
  }
  traj.point_count = static_cast<std::uint8_t>(keep);
}

}  // namespace

int main() {
  gf_ara::com::binding::iceoryx::InitRuntime("gf-planning-driving");

  gf_fs_envelope::InitEnvelopeFromMounts();
  std::cout << "gf-planning-driving_plus: envelope side=" << gf_fs_envelope::SideLatM()
            << " rear=" << gf_fs_envelope::RearCapM() << "\n";

  gf_ara::runtime::ProcessSupervisor supervisor;
  if (!supervisor.Start(kProcess)) {
    std::cerr << "[ERROR] planning.driving_plus: ProcessSupervisor.Start failed\n";
    return EXIT_FAILURE;
  }

  gf_gen::Perception_MESSAGE_Out_StProxy perc_sub{};
  gf_gen::EgoMotionProxy ego_sub{};
  gf_gen::FreespaceNearProxy fs_sub{};
  gf_gen::SurroundWorldProxy surround_sub{};
  gf_gen::Perception_Rear_Out_StProxy rcm_sub{};
  gf_gen::TrajectorySkeleton traj_pub{};
  gf_gen::FreespaceSkeleton fs_pub{};

  std::optional<gf_gen::EgoMotion> last_ego;
  std::optional<gf_gen::Perception_MESSAGE_Out_St> last_perc;
  std::optional<gf_gen::FreespaceNear> last_fs;
  std::optional<gf_gen::SurroundWorld> last_surround;
  std::optional<gf_gen::Perception_Rear_Out_St> last_rcm;
  std::uint64_t last_ego_rx_ns = 0;
  std::uint64_t last_near_rx_ns = 0;
  std::uint64_t last_surround_rx_ns = 0;
  std::uint64_t last_rcm_rx_ns = 0;
  float D_see_prev = 0.0f;
  float T_plan_prev = 0.0f;
  std::uint64_t seq = 0;
  std::string last_lc_reason;
  bool lc_was_ego_bad = false;
  bool lc_was_near_bad = false;
  bool lc_was_rcm_bad = false;
  gf_app::EnsureDiagLogSinks();
  gf_app::FrameWatch rx_ego;
  gf_app::FrameWatch rx_perc;
  gf_app::FrameWatch tx_traj;
  rx_ego.Init("plan", "rx.ego");
  rx_ego.BindService("EgoMotion");
  rx_perc.Init("plan", "rx.perc");
  rx_perc.BindService("Perception_MESSAGE_Out_St");
  rx_perc.BindCameraCeiling();
  tx_traj.Init("plan", "tx.traj");
  tx_traj.BindService("Trajectory");
  std::uint64_t last_perc_ts = 0;
  bool have_planned = false;
  bool perc_edge = false;
  bool surround_edge = false;
  bool rcm_edge = false;
  bool near_edge = false;

  gf_ara::com::binding::iceoryx::EventWaitSet<8> waitset;
  if (!waitset.AttachProxy(ego_sub, kIdEgo) || !waitset.AttachProxy(perc_sub, kIdPerc) ||
      !waitset.AttachProxy(surround_sub, kIdSurround) || !waitset.AttachProxy(rcm_sub, kIdRcm) ||
      !waitset.AttachProxy(fs_sub, kIdNear)) {
    std::cerr << "[ERROR] planning.driving_plus: EventWaitSet attach failed\n";
    return EXIT_FAILURE;
  }

  std::cout << "gf-planning-driving_plus: start (Freespace; EventWaitSet; "
               "Traj=perc edge; FS=perc|surround|rcm|near; lc_inhibit=P1+P2)\n";

  while (!iox::posix::hasTerminationRequested()) {
    supervisor.Tick();
    if (supervisor.ExitForEmRestart()) {
      return gf_ara::exec::kEmRestartExitCode;
    }

    (void)waitset.TimedWaitMs(kWaitSliceMs);

    for (;;) {
      auto t = ego_sub.Take();
      if (!t || !t.Value().has_value()) {
        break;
      }
      last_ego = *t.Value();
      last_ego_rx_ns = now_ns();
      rx_ego.Observe(0, last_ego->timestamp_ns, false, true);
    }
    for (;;) {
      auto t = perc_sub.Take();
      if (!t || !t.Value().has_value()) {
        break;
      }
      last_perc = *t.Value();
      perc_edge = true;
    }
    for (;;) {
      auto t = fs_sub.Take();
      if (!t || !t.Value().has_value()) {
        break;
      }
      last_fs = *t.Value();
      last_near_rx_ns = now_ns();
      near_edge = true;
    }
    for (;;) {
      auto t = surround_sub.Take();
      if (!t || !t.Value().has_value()) {
        break;
      }
      last_surround = *t.Value();
      last_surround_rx_ns = now_ns();
      surround_edge = true;
    }
    for (;;) {
      auto t = rcm_sub.Take();
      if (!t || !t.Value().has_value()) {
        break;
      }
      last_rcm = *t.Value();
      last_rcm_rx_ns = now_ns();
      rcm_edge = true;
    }

    if (!last_perc || !last_ego) {
      continue;
    }

    const auto& ego = *last_ego;
    const std::uint64_t perc_ts =
        last_perc->Perception_DYN_OBJ_Out.m_time_stamp * 1000ULL;
    // FrameWatch = sample identity: only on real Take edge (hold-last must not re-Observe).
    if (perc_edge) {
      rx_perc.Observe(0, perc_ts, false, true);
    }

    const bool need_traj = perc_edge && (!have_planned || perc_ts != last_perc_ts);
    const bool need_fs = perc_edge || surround_edge || rcm_edge || near_edge;
    perc_edge = surround_edge = rcm_edge = near_edge = false;
    if (!need_traj && !need_fs) {
      continue;
    }

    const PercView view = ExtractPerc(*last_perc);

    const float d_empty = gf_fs_envelope::kFsFrontFarCapM;
    const float lane_w = view.lane.valid ? view.lane.width_m : 3.5f;
    gf_plan_fs::FsOccSample occ_samples[oct_gen::kObjNMax]{};
    gf_plan_fs::LaneClearSample clear_samples[oct_gen::kObjNMax]{};
    int n_occ = 0;
    int n_clear = 0;
    for (int i = 0; i < view.nobj && n_occ < oct_gen::kObjNMax; ++i) {
      if (std::fabs(view.obj[i].d) < 0.3f) {
        continue;
      }
      if (gf_octave_planning::plan_is_reg_stop(view.obj[i].cls)) {
        continue;  // stop line is v_reg, not occupy clear
      }
      const auto cls = static_cast<std::uint8_t>(view.obj[i].cls);
      const bool hard = gf_plan_fs::IsHardStaticCls(cls);
      const float half_w = hard ? 0.45f : 0.95f;
      const float half_l =
          0.5f * std::max(hard ? 0.6f : 3.0f,
                          view.obj[i].len_m > 0.5f ? view.obj[i].len_m : 4.5f);
      PushFsOccClear(occ_samples, &n_occ, clear_samples, &n_clear, oct_gen::kObjNMax,
                     view.obj[i].d, view.obj[i].lat, cls, view.obj_id[i], view.obj_assign[i],
                     half_l, half_w);
    }
    // RCM / Surround → occupy only (NearObst side/rear). Never cut forward left/right clear.
    if (last_rcm && last_rcm_rx_ns != 0 && (now_ns() - last_rcm_rx_ns) <= kLcStaleNs * 3) {
      const int n_r = std::min(16, static_cast<int>(last_rcm->n_obj));
      for (int i = 0; i < n_r; ++i) {
        const auto& o = last_rcm->objects[i];
        if (o.object_id == 0) {
          continue;
        }
        PushFsOcc(occ_samples, &n_occ, oct_gen::kObjNMax, o.long_dist_m, o.lat_dist_m,
                  o.object_class, 1.8f, 0.95f);
      }
    }
    if (last_surround && last_surround_rx_ns != 0 &&
        (now_ns() - last_surround_rx_ns) <= kLcStaleNs * 3) {
      const int n_s = std::min(16, static_cast<int>(last_surround->n_obj));
      for (int i = 0; i < n_s; ++i) {
        const auto& o = last_surround->objects[i];
        if (o.object_id == 0) {
          continue;
        }
        PushFsOcc(occ_samples, &n_occ, oct_gen::kObjNMax, o.long_dist_m, o.lat_dist_m,
                  o.object_class, 1.8f, 0.95f);
      }
    }
    gf_plan_fs::LaneAssignConflict conflicts[8]{};
    int n_conflicts = 0;
    const gf_plan_fs::LaneClearFwd lane_clear = gf_plan_fs::ComputeLaneClearFwd(
        view.lane_bands, clear_samples, n_clear, d_empty, conflicts, &n_conflicts, 8);

    // Host clear only — neighbor objs do not cut host fuse / path.
    gf_plan_fs::FsDriving fs_drv =
        gf_plan_fs::FuseDrivingFs(lane_clear.host_m, last_fs ? &*last_fs : nullptr);

    const std::uint64_t tnow = now_ns();
    const bool ego_ok =
        last_ego.has_value() && last_ego_rx_ns != 0 &&
        (tnow - last_ego_rx_ns) <= kLcStaleNs;
    const bool near_ok =
        last_fs.has_value() && last_fs->valid != 0 && last_near_rx_ns != 0 &&
        (tnow - last_near_rx_ns) <= kLcStaleNs;
    const bool rcm_ok =
        last_rcm.has_value() && last_rcm->valid != 0 && last_rcm_rx_ns != 0 &&
        (tnow - last_rcm_rx_ns) <= kLcStaleNs;
    // P1: LC corridor not ready → always inhibit (do not steer). Hook uses LcCorridor.ready.
    const gf_plan_fs::LcCorridor lc_corr{};  // valid/ready false until corridor geometry exists
    const gf_plan_fs::LcGate lc =
        gf_plan_fs::MakeLcGate(ego_ok, near_ok, rcm_ok, lc_corr.ready);
    gf_plan_fs::ApplyLcInhibit(&fs_drv, lc);
    // P2: DTC only for ego/near/rcm edges; corridor-only is expected until P3.
    ReportLcFaultEdge(!ego_ok, &lc_was_ego_bad, "LcInhibitEgo");
    ReportLcFaultEdge(!near_ok, &lc_was_near_bad, "LcInhibitSurround");
    ReportLcFaultEdge(!rcm_ok, &lc_was_rcm_bad, "LcInhibitRcm");

    // Host clear enters D_see via x_end clamp. LC flags gated; no steer.
    float x_end_use = view.lane.x_end;
    if (view.lane.valid && fs_drv.d_front_m > 0.5f) {
      x_end_use = std::min(x_end_use, fs_drv.d_front_m);
    }

    if (need_fs) {
      gf_gen::Freespace fs_out{};
      gf_plan_fs::ComposeFreespace(d_empty, lane_w, last_fs ? &*last_fs : nullptr, occ_samples,
                                   n_occ, perc_ts, &fs_out, gf_plan_fs::DefaultFrontCam(),
                                   view.road_left, view.road_right, view.hard_walls,
                                   view.n_hard_walls, view.lane_bands, &lane_clear,
                                   gf_plan_fs::LaneEnvMode::UnionAll, &lc_corr);
      fs_out.timestamp_ns = perc_ts;
      (void)fs_pub.Send(fs_out);
    }

    if (need_traj) {
      const float v_sign_max =
          view.v_sign_max_mps > 0.5f ? view.v_sign_max_mps : 1.0e6f;
      const float v_sign_min = view.v_sign_min_mps;
      const auto tick = oct_gen::m_plan_tick(
          ego.speed_mps, ego.steer_angle_deg, view.lane.valid, view.lane.e_y, view.lane.c0,
          view.lane.c1, view.lane.c2, view.lane.c3, x_end_use, view.lane.conf,
          view.lane.lane_count, view.nobj ? view.obj : nullptr, view.nobj, D_see_prev, T_plan_prev,
          v_sign_max, v_sign_min);
      D_see_prev = tick.D_see;
      T_plan_prev = tick.T_plan;

      gf_gen::Trajectory traj{};
      ApplyTick(tick, ego, view, traj);
      ClipPathToLaneEnvelope(traj, fs_drv.d_front_m, view.lane_bands.host_l,
                             view.lane_bands.host_r);
      traj.gear_shift_second = 0;  // LC P1: inhibit always; never LC intent bit
      traj.timestamp_ns = perc_ts;

      const char* lc_reason = lc.Reason();
      if (lc_reason != last_lc_reason) {
        std::cout << "[lc] inhibit=" << (lc.inhibit ? 1 : 0) << " reason=" << lc_reason
                  << " ego=" << (lc.ego_ok ? 1 : 0) << " near=" << (lc.near_ok ? 1 : 0)
                  << " rcm=" << (lc.rcm_ok ? 1 : 0)
                  << " corridor=" << (lc.corridor_ready ? 1 : 0)
                  << " cand=" << (fs_drv.lane_change_candidate ? 1 : 0) << std::endl;
        last_lc_reason = lc_reason;
      }

      if (static_cast<bool>(traj_pub.Send(traj))) {
        tx_traj.Observe(seq, traj.timestamp_ns);
        last_perc_ts = perc_ts;
        have_planned = true;
        ++seq;
      }
    } else {
      const char* lc_reason = lc.Reason();
      if (lc_reason != last_lc_reason) {
        std::cout << "[lc] inhibit=" << (lc.inhibit ? 1 : 0) << " reason=" << lc_reason
                  << " ego=" << (lc.ego_ok ? 1 : 0) << " near=" << (lc.near_ok ? 1 : 0)
                  << " rcm=" << (lc.rcm_ok ? 1 : 0)
                  << " corridor=" << (lc.corridor_ready ? 1 : 0)
                  << " cand=" << (fs_drv.lane_change_candidate ? 1 : 0) << std::endl;
        last_lc_reason = lc_reason;
      }
    }
  }
  waitset.MarkForDestruction();
  return EXIT_SUCCESS;
}
