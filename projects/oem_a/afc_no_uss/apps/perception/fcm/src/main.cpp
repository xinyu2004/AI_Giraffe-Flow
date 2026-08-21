#include "detect_backend.hpp"
#include "frame_source.hpp"

#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_ara/runtime/process_bringup.hpp"
#include "gf_gen/proxy/ego_motion_proxy.hpp"
#include "gf_gen/proxy/perception__in__st_proxy.hpp"
#include "gf_gen/skeleton/perception_message__out__st_skeleton.hpp"

#if __has_include("gf_gen/frame_ingest_config.hpp")
#include "gf_gen/frame_ingest_config.hpp"
#define GF_FCM_HAS_FRAME_INGEST 1
#endif

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <optional>
#include <sstream>
#include <string>
#include <thread>
#include <utility>

namespace {

constexpr const char* kProcess = "perception.fcm";

std::uint32_t EnvU32(const char* key, std::uint32_t def) {
  const char* v = std::getenv(key);
  if (!v || !v[0]) {
    return def;
  }
  return static_cast<std::uint32_t>(std::strtoul(v, nullptr, 10));
}

std::string TruthPath() {
  const char* v = std::getenv("GF_CARLA_TRUTH_PATH");
#if defined(GF_FCM_HAS_FRAME_INGEST)
  if (!v || !v[0]) {
    v = gf_gen::frame_ingest::kTruthPath;
  }
#endif
  return (v && v[0]) ? std::string(v) : std::string("runtime_ipc/carla_truth.json");
}

bool JsonF32(const std::string& js, const char* key, float* out) {
  const std::string pat = std::string("\"") + key + "\"";
  auto pos = js.find(pat);
  if (pos == std::string::npos) {
    return false;
  }
  pos = js.find(':', pos + pat.size());
  if (pos == std::string::npos) {
    return false;
  }
  ++pos;
  while (pos < js.size() && (js[pos] == ' ' || js[pos] == '\t')) {
    ++pos;
  }
  char* end = nullptr;
  const float v = std::strtof(js.c_str() + pos, &end);
  if (end == js.c_str() + pos) {
    return false;
  }
  *out = v;
  return true;
}

bool JsonU64(const std::string& js, const char* key, std::uint64_t* out) {
  const std::string pat = std::string("\"") + key + "\"";
  auto pos = js.find(pat);
  if (pos == std::string::npos) {
    return false;
  }
  pos = js.find(':', pos + pat.size());
  if (pos == std::string::npos) {
    return false;
  }
  ++pos;
  while (pos < js.size() && (js[pos] == ' ' || js[pos] == '\t')) {
    ++pos;
  }
  char* end = nullptr;
  const unsigned long long v = std::strtoull(js.c_str() + pos, &end, 10);
  if (end == js.c_str() + pos) {
    return false;
  }
  *out = static_cast<std::uint64_t>(v);
  return true;
}

bool JsonU32(const std::string& js, const char* key, std::uint32_t* out) {
  std::uint64_t v = 0;
  if (!JsonU64(js, key, &v)) {
    return false;
  }
  *out = static_cast<std::uint32_t>(v);
  return true;
}

bool JsonI32(const std::string& js, const char* key, int* out) {
  const std::string pat = std::string("\"") + key + "\"";
  auto pos = js.find(pat);
  if (pos == std::string::npos) {
    return false;
  }
  pos = js.find(':', pos + pat.size());
  if (pos == std::string::npos) {
    return false;
  }
  ++pos;
  while (pos < js.size() && (js[pos] == ' ' || js[pos] == '\t')) {
    ++pos;
  }
  char* end = nullptr;
  const long v = std::strtol(js.c_str() + pos, &end, 10);
  if (end == js.c_str() + pos) {
    return false;
  }
  *out = static_cast<int>(v);
  return true;
}

struct TruthSnapshot {
  float lead_distance_m{0.0f};
  float lead_rel_speed_mps{0.0f};
  float lead_lat_m{0.0f};
  float lead_heading_rad{0.0f};
  std::uint8_t lead_lane_assignment{3};  // HOST
  std::uint64_t timestamp_ns{0};
  std::uint64_t seq{0};
  bool lead_valid{false};
  bool file_ok{false};  // truth file opened and parsed at least lead or lane keys
  // Lanes from CARLA truth (0 count → FCM falls back to host-only ±1.75)
  std::uint8_t lane_count{0};
  std::uint8_t ego_lane_index_from_left{0};
  float lane_width_m{3.5f};
  float host_left_c0{1.75f};
  float host_right_c0{-1.75f};
  float host_c1{0.0f};
  float host_c2{0.0f};
  float host_left_c1{0.0f};
  float host_right_c1{0.0f};
  float host_left_c2{0.0f};
  float host_right_c2{0.0f};
  std::uint8_t host_left_type{1};
  std::uint8_t host_right_type{1};
  std::uint8_t adj_n{0};
  std::uint8_t adj_side[4]{};
  float adj_c0[4]{};
  float adj_c1[4]{};
  float adj_c2[4]{};
  std::uint8_t adj_type[4]{};
  // Multi dyn objects (flat obj{i}_*)
  std::uint8_t dyn_n{0};
  std::uint8_t vd_count{0};
  std::uint8_t ped_count{0};
  std::uint8_t cipv_id{0};
  std::uint8_t obj_id[13]{};
  std::uint8_t obj_class[13]{};
  float obj_long[13]{};
  float obj_lat[13]{};
  float obj_heading[13]{};
  float obj_len[13]{};
  float obj_wid[13]{};
  float obj_rel_v[13]{};
  std::uint8_t obj_assign[13]{};
  std::uint8_t obj_ped[13]{};
  // Lane poly quality (truth → Availability / Confidence / VR_End)
  std::uint8_t lane_avail{2};   // 0=NA 1=pred 2=detected
  float lane_conf{0.95f};
  float lane_vr_end_m{130.0f};
};

TruthSnapshot ReadTruth(const std::string& path) {
  TruthSnapshot t{};
  if (path.empty()) {
    return t;
  }
  std::ifstream in(path);
  if (!in) {
    return t;
  }
  std::ostringstream oss;
  oss << in.rdbuf();
  const std::string js = oss.str();
  if (js.empty()) {
    return t;
  }
  t.file_ok = true;
  float dist = 0.0f;
  if (JsonF32(js, "lead_distance_m", &dist)) {
    t.lead_distance_m = dist;
    t.lead_valid = dist > 0.5f && dist <= 130.0f;
  }
  (void)JsonF32(js, "lead_rel_speed_mps", &t.lead_rel_speed_mps);
  (void)JsonF32(js, "lead_lat_m", &t.lead_lat_m);
  (void)JsonF32(js, "lead_heading_rad", &t.lead_heading_rad);
  int assign = 3;
  if (JsonI32(js, "lead_lane_assignment", &assign) && assign >= 0 && assign <= 5) {
    t.lead_lane_assignment = static_cast<std::uint8_t>(assign);
  }
  (void)JsonU64(js, "timestamp_ns", &t.timestamp_ns);
  (void)JsonU64(js, "seq", &t.seq);

  std::uint32_t lc = 0;
  if (JsonU32(js, "lane_count", &lc) && lc > 0) {
    t.lane_count = static_cast<std::uint8_t>(std::min<std::uint32_t>(lc, 16));
  }
  std::uint32_t ei = 0;
  if (JsonU32(js, "ego_lane_index_from_left", &ei)) {
    t.ego_lane_index_from_left = static_cast<std::uint8_t>(ei);
  }
  (void)JsonF32(js, "lane_width_m", &t.lane_width_m);
  (void)JsonF32(js, "host_left_c0", &t.host_left_c0);
  (void)JsonF32(js, "host_right_c0", &t.host_right_c0);
  (void)JsonF32(js, "host_c1", &t.host_c1);
  (void)JsonF32(js, "host_c2", &t.host_c2);
  (void)JsonF32(js, "host_left_c1", &t.host_left_c1);
  (void)JsonF32(js, "host_right_c1", &t.host_right_c1);
  (void)JsonF32(js, "host_left_c2", &t.host_left_c2);
  (void)JsonF32(js, "host_right_c2", &t.host_right_c2);
  std::uint32_t hlt = 1, hrt = 1;
  if (JsonU32(js, "host_left_type", &hlt) && hlt <= 2) {
    t.host_left_type = static_cast<std::uint8_t>(hlt);
  }
  if (JsonU32(js, "host_right_type", &hrt) && hrt <= 2) {
    t.host_right_type = static_cast<std::uint8_t>(hrt);
  }
  std::uint32_t an = 0;
  if (JsonU32(js, "adj_n", &an)) {
    t.adj_n = static_cast<std::uint8_t>(std::min<std::uint32_t>(an, 4));
  }
  for (std::uint8_t i = 0; i < t.adj_n; ++i) {
    const std::string sk = "adj" + std::to_string(i) + "_side";
    const std::string ck = "adj" + std::to_string(i) + "_c0";
    const std::string c1k = "adj" + std::to_string(i) + "_c1";
    const std::string tk = "adj" + std::to_string(i) + "_type";
    int side = 0;
    float c0 = 0.0f;
    if (JsonI32(js, sk.c_str(), &side) && JsonF32(js, ck.c_str(), &c0)) {
      t.adj_side[i] = static_cast<std::uint8_t>(side);
      t.adj_c0[i] = c0;
      (void)JsonF32(js, c1k.c_str(), &t.adj_c1[i]);
      const std::string c2k = "adj" + std::to_string(i) + "_c2";
      (void)JsonF32(js, c2k.c_str(), &t.adj_c2[i]);
      std::uint32_t ty = 2;
      if (JsonU32(js, tk.c_str(), &ty) && ty >= 1 && ty <= 2) {
        t.adj_type[i] = static_cast<std::uint8_t>(ty);
      } else {
        t.adj_type[i] = 2;
      }
    }
  }

  std::uint32_t lav = 2;
  if (JsonU32(js, "lane_avail", &lav) && lav <= 2) {
    t.lane_avail = static_cast<std::uint8_t>(lav);
  }
  if (!JsonF32(js, "lane_conf", &t.lane_conf)) {
    t.lane_conf = (t.lane_avail == 0) ? 0.05f : 0.95f;
  }
  if (!JsonF32(js, "lane_vr_end_m", &t.lane_vr_end_m)) {
    t.lane_vr_end_m = (t.lane_avail == 0) ? 0.0f : 130.0f;
  }
  if (t.lane_vr_end_m < 0.0f) {
    t.lane_vr_end_m = 0.0f;
  }
  if (t.lane_vr_end_m > 130.0f) {
    t.lane_vr_end_m = 130.0f;
  }

  std::uint32_t dyn_n = 0;
  if (JsonU32(js, "dyn_n", &dyn_n)) {
    t.dyn_n = static_cast<std::uint8_t>(std::min<std::uint32_t>(dyn_n, 13));
  }
  std::uint32_t vd = 0, ped = 0, cipv = 0;
  if (JsonU32(js, "vd_count", &vd)) {
    t.vd_count = static_cast<std::uint8_t>(vd);
  }
  if (JsonU32(js, "ped_count", &ped)) {
    t.ped_count = static_cast<std::uint8_t>(ped);
  }
  if (JsonU32(js, "cipv_id", &cipv)) {
    t.cipv_id = static_cast<std::uint8_t>(cipv);
  }
  for (std::uint8_t i = 0; i < t.dyn_n; ++i) {
    const std::string pref = "obj" + std::to_string(i) + "_";
    std::uint32_t id = 0, cls = 1, assign = 3, is_ped = 0;
    (void)JsonU32(js, (pref + "id").c_str(), &id);
    (void)JsonU32(js, (pref + "class").c_str(), &cls);
    (void)JsonF32(js, (pref + "long").c_str(), &t.obj_long[i]);
    (void)JsonF32(js, (pref + "lat").c_str(), &t.obj_lat[i]);
    (void)JsonF32(js, (pref + "heading").c_str(), &t.obj_heading[i]);
    (void)JsonF32(js, (pref + "len").c_str(), &t.obj_len[i]);
    (void)JsonF32(js, (pref + "wid").c_str(), &t.obj_wid[i]);
    (void)JsonF32(js, (pref + "rel_v").c_str(), &t.obj_rel_v[i]);
    (void)JsonU32(js, (pref + "assign").c_str(), &assign);
    (void)JsonU32(js, (pref + "ped").c_str(), &is_ped);
    t.obj_id[i] = static_cast<std::uint8_t>(id ? id : (i + 1));
    t.obj_class[i] = static_cast<std::uint8_t>(cls);
    t.obj_assign[i] = static_cast<std::uint8_t>(assign);
    t.obj_ped[i] = static_cast<std::uint8_t>(is_ped);
    if (t.obj_len[i] < 0.3f) {
      t.obj_len[i] = is_ped ? 0.6f : 4.5f;
    }
    if (t.obj_wid[i] < 0.3f) {
      t.obj_wid[i] = is_ped ? 0.6f : 1.8f;
    }
  }
  return t;
}

void ClearOut(gf_gen::Perception_MESSAGE_Out_St& out) {
  out = gf_gen::Perception_MESSAGE_Out_St{};
}

void FillLanesFromTruth(gf_gen::Perception_MESSAGE_Out_St& out,
                        const TruthSnapshot& truth,
                        std::uint64_t timestamp_ns,
                        std::uint32_t frame_id) {
  constexpr float kVrCap = 130.0f;
  float left_c0 = truth.host_left_c0;
  float right_c0 = truth.host_right_c0;
  float left_c1 = truth.host_left_c1 != 0.0f ? truth.host_left_c1 : truth.host_c1;
  float right_c1 = truth.host_right_c1 != 0.0f ? truth.host_right_c1 : truth.host_c1;
  float left_c2 = truth.host_left_c2 != 0.0f ? truth.host_left_c2 : truth.host_c2;
  float right_c2 = truth.host_right_c2 != 0.0f ? truth.host_right_c2 : truth.host_c2;
  std::uint8_t left_type = truth.host_left_type ? truth.host_left_type : 1;
  std::uint8_t right_type = truth.host_right_type ? truth.host_right_type : 1;
  float width = truth.lane_width_m;
  std::uint8_t avail = truth.lane_avail;
  float conf = truth.lane_conf;
  float vr_end = truth.lane_vr_end_m;
  if (vr_end > kVrCap) {
    vr_end = kVrCap;
  }
  if (truth.lane_count == 0) {
    left_c0 = 1.75f;
    right_c0 = -1.75f;
    width = 3.5f;
    left_c1 = right_c1 = 0.0f;
    left_c2 = right_c2 = 0.0f;
    left_type = 1;
    right_type = 1;
    avail = 0;
    conf = 0.0f;
    vr_end = 0.0f;
  }
  if (width < 0.5f) {
    width = std::max(2.5f, left_c0 - right_c0);
  }
  // Invalid ego-frame poly: do not publish drawable host/adj geometry.
  if (avail == 0 || vr_end < 0.5f || conf < 0.1f) {
    avail = 0;
    conf = std::min(conf, 0.05f);
    vr_end = 0.0f;
    left_c2 = right_c2 = 0.0f;
  }

  auto& lh = out.Perception_LH_Out;
  lh.m_frame_id = frame_id;
  lh.m_time_stamp = timestamp_ns / 1000ULL;
  lh.m_hostline_num = (avail == 0) ? 0 : 2;
  lh.m_LH_Estimated_Width = width;

  auto fill_host = [&](gf_gen::HostLine_St& line, std::uint8_t side, float c0,
                       float c1, float c2, std::uint8_t mark_type,
                       std::uint8_t track_id) {
    line.LH_Track_ID = track_id;
    line.m_LH_Side = side;
    line.m_LH_Confidence = conf;
    line.m_LH_Availability_State = avail;
    line.m_LH_Lanemark_Type = mark_type;
    line.m_LH_First_VR_Start = 0.0f;
    line.m_LH_First_VR_End = vr_end;
    line.m_LH_Marker_Width = 0.15f;
    line.m_LH_Line_First_C0 = (avail == 0) ? 0.0f : c0;
    line.m_LH_Line_First_C1 = (avail == 0) ? 0.0f : c1;
    line.m_LH_Line_First_C2 = (avail == 0) ? 0.0f : c2;
    line.m_LH_Line_First_C3 = 0.0f;
    line.m_LH_Color = 1;
    line.m_LH_DLM_Type = 0;
    line.m_LH_DECEL_Type = 0;
    line.m_LH_Crossing = false;
  };
  if (avail != 0) {
    fill_host(lh.m_hostline[0], 1, left_c0, left_c1, left_c2, left_type, 1);
    fill_host(lh.m_hostline[1], 2, right_c0, right_c1, right_c2, right_type, 2);
  }

  auto& la = out.Perception_LA_Out;
  la.m_frame_id = frame_id;
  la.m_time_stamp = timestamp_ns / 1000ULL;
  // Adj only when host poly is healthy (detected); degraded/invalid → no adj.
  const std::uint8_t adj_n =
      (avail == 2) ? truth.adj_n : static_cast<std::uint8_t>(0);
  la.m_adj_line_num = adj_n;
  for (std::uint8_t i = 0; i < adj_n && i < 4; ++i) {
    auto& line = la.m_adj_line[i];
    line.LA_Track_ID = static_cast<std::uint8_t>(10 + i);
    line.m_LA_Confidence = conf * 0.95f;
    line.m_LA_Availability_State = avail;
    line.m_LA_View_Range_Start = 0.0f;
    line.m_LA_View_Range_End = vr_end;
    line.m_LA_Lanemark_Type = truth.adj_type[i] ? truth.adj_type[i] : 2;
    line.m_LA_Line_Side = truth.adj_side[i];
    line.m_LA_Line_C0 = truth.adj_c0[i];
    line.m_LA_Line_C1 = truth.adj_c1[i];
    line.m_LA_Line_C2 = truth.adj_c2[i];
    line.m_LA_Line_C3 = 0.0f;
  }
}

void FillOutFromTruth(gf_gen::Perception_MESSAGE_Out_St& out,
                      const TruthSnapshot& truth,
                      std::uint64_t timestamp_ns,
                      std::uint32_t frame_id) {
  ClearOut(out);
  FillLanesFromTruth(out, truth, timestamp_ns, frame_id);
  auto& dyn = out.Perception_DYN_OBJ_Out;
  dyn.m_frame_id = frame_id;
  dyn.m_time_stamp = timestamp_ns / 1000ULL;
  if (truth.dyn_n > 0) {
    dyn.m_OBJ_VD_Count = truth.vd_count;
    dyn.m_OBJ_Ped_Count = truth.ped_count;
    dyn.m_OBJ_VD_CIPV_ID = truth.cipv_id;
    const std::uint8_t n = std::min<std::uint8_t>(truth.dyn_n, 13);
    for (std::uint8_t i = 0; i < n; ++i) {
      auto& obj = dyn.m_Obj_item[i];
      obj.m_OBJ_ID = truth.obj_id[i] ? truth.obj_id[i] : static_cast<std::uint8_t>(i + 1);
      obj.m_OBJ_Object_Class = truth.obj_class[i] ? truth.obj_class[i] : 1;
      obj.m_OBJ_Long_Distance = truth.obj_long[i];
      obj.m_OBJ_Lat_Distance = truth.obj_lat[i];
      obj.m_OBJ_Relative_Long_Velocity = truth.obj_rel_v[i];
      obj.m_OBJ_Relative_Lat_Velocity = 0.0f;
      obj.m_OBJ_Lane_Assignment = truth.obj_assign[i] ? truth.obj_assign[i] : 3;
      obj.m_OBJ_Heading = truth.obj_heading[i];
      obj.m_OBJ_Width = truth.obj_wid[i] > 0.2f ? truth.obj_wid[i] : 1.8f;
      obj.m_OBJ_Length = truth.obj_len[i] > 0.2f ? truth.obj_len[i] : 4.5f;
      obj.m_OBJ_Height = truth.obj_ped[i] ? 1.7f : 1.5f;
      obj.m_OBJ_Existence_Probability = 0.95f;
      obj.m_OBJ_Object_Age = 1;
      obj.m_OBJ_Class_Probability = 0.9f;
    }
    return;
  }
  if (!truth.lead_valid) {
    dyn.m_OBJ_VD_Count = 0;
    dyn.m_OBJ_Ped_Count = 0;
    dyn.m_OBJ_VD_CIPV_ID = 0;
    return;
  }
  dyn.m_OBJ_VD_Count = 1;
  dyn.m_OBJ_Ped_Count = 0;
  dyn.m_OBJ_VD_CIPV_ID = 1;
  auto& obj = dyn.m_Obj_item[0];
  obj.m_OBJ_ID = 1;
  obj.m_OBJ_Object_Class = 1;
  obj.m_OBJ_Long_Distance = truth.lead_distance_m;
  obj.m_OBJ_Lat_Distance = truth.lead_lat_m;
  obj.m_OBJ_Relative_Long_Velocity = truth.lead_rel_speed_mps;
  obj.m_OBJ_Relative_Lat_Velocity = 0.0f;
  obj.m_OBJ_Lane_Assignment = truth.lead_lane_assignment;
  obj.m_OBJ_Heading = truth.lead_heading_rad;
  obj.m_OBJ_Width = 1.8f;
  obj.m_OBJ_Length = 4.5f;
  obj.m_OBJ_Height = 1.5f;
  obj.m_OBJ_Existence_Probability = 0.95f;
  obj.m_OBJ_Object_Age = 1;
}

gf_gen::Perception_MESSAGE_Out_St MakeEmptyOut(std::uint64_t timestamp_ns) {
  gf_gen::Perception_MESSAGE_Out_St out{};
  FillOutFromTruth(out, TruthSnapshot{}, timestamp_ns, 0);
  return out;
}

gf_gen::Perception_MESSAGE_Out_St MakeFromDetect(
    std::uint64_t timestamp_ns, const gf_fcm::DetectResult& d) {
  (void)d;
  return MakeEmptyOut(timestamp_ns);
}

const char* KindName(gf_fcm::FrameSourceKind k) {
  switch (k) {
    case gf_fcm::FrameSourceKind::None:
      return "none";
    case gf_fcm::FrameSourceKind::Synth:
      return "synth";
    case gf_fcm::FrameSourceKind::File:
      return "file";
    case gf_fcm::FrameSourceKind::CarlaFile:
      return "carla_file";
  }
  return "?";
}

}  // namespace

int main() {
  gf_ara::com::binding::iceoryx::InitRuntime("gf-perception-fcm");

  gf_ara::runtime::ProcessSupervisor supervisor;
  if (!supervisor.Start(kProcess)) {
    std::cerr << "[ERROR] perception.fcm: ProcessSupervisor.Start failed\n";
    return EXIT_FAILURE;
  }

  const auto frame_kind = gf_fcm::ParseFrameSource(nullptr);
  const auto backend = gf_fcm::ParseBackend(nullptr);
  // Keep-alive cadence when In/Ego/camera stall — republish frozen Out, never clear.
  const std::uint32_t keep_ms = EnvU32("GF_OUT_KEEPALIVE_MS", 50);
  const char* model_env = std::getenv("GF_ONNX_MODEL");
  const std::string model_path = (model_env && model_env[0]) ? model_env : "";
  const std::string truth_path = TruthPath();

  gf_fcm::FrameSource frames(frame_kind);
  gf_gen::Perception_In_StProxy in_sub{};
  gf_gen::EgoMotionProxy ego_sub{};
  gf_gen::Perception_MESSAGE_Out_StSkeleton out_pub{};

  std::uint64_t out_seq = 0;
  std::uint64_t last_keep_ns = 0;
  gf_gen::Perception_MESSAGE_Out_St last_out{};
  bool have_frozen = false;
  std::uint64_t last_truth_seq = 0;
  std::uint64_t last_truth_ts = 0;
  std::uint64_t freeze_log_at = 0;

  std::cout << "gf-perception-fcm: start frame_source=" << KindName(frame_kind)
            << " backend="
            << (backend == gf_fcm::BackendKind::Onnx ? "onnx" : "stub")
            << " truth=" << truth_path
            << " (no update → freeze last Out; link stays up)"
            << " keepalive_ms=" << keep_ms << std::endl;

  while (!iox::posix::hasTerminationRequested()) {
    supervisor.Tick();
    if (supervisor.ExitForEmRestart()) {
      return gf_ara::exec::kEmRestartExitCode;
    }

    std::optional<std::uint32_t> in_frame;
    std::optional<std::uint64_t> in_ts;
    {
      auto taken = in_sub.Take();
      if (taken && taken.Value().has_value()) {
        in_frame = taken.Value()->ipc_frame_counter;
        in_ts = taken.Value()->timestamp_ns;
      }
    }

    const TruthSnapshot truth = ReadTruth(truth_path);
    const bool truth_fresh =
        truth.file_ok &&
        (truth.seq != last_truth_seq || truth.timestamp_ns != last_truth_ts ||
         (!have_frozen &&
          (truth.lead_valid || truth.lane_count > 0 || truth.dyn_n > 0)));

    auto publish_out = [&](std::uint64_t ts, std::uint32_t frame_id) {
      gf_gen::Perception_MESSAGE_Out_St out{};
      const char* mode = "update";
      if (truth_fresh) {
        FillOutFromTruth(out, truth, ts, frame_id);
        last_out = out;
        have_frozen = true;
        last_truth_seq = truth.seq;
        last_truth_ts = truth.timestamp_ns;
      } else if (have_frozen) {
        // Keep link: republish last perception (frozen). Refresh stamp only.
        out = last_out;
        out.Perception_DYN_OBJ_Out.m_time_stamp = ts / 1000ULL;
        out.Perception_LH_Out.m_time_stamp = ts / 1000ULL;
        out.Perception_LA_Out.m_time_stamp = ts / 1000ULL;
        out.Perception_DYN_OBJ_Out.m_frame_id = frame_id;
        out.Perception_LH_Out.m_frame_id = frame_id;
        out.Perception_LA_Out.m_frame_id = frame_id;
        mode = "freeze";
      } else {
        // Never had truth yet — empty keep-alive
        FillOutFromTruth(out, TruthSnapshot{}, ts, frame_id);
        mode = "idle";
      }
      if (!static_cast<bool>(out_pub.Send(out))) {
        return;
      }
      const auto& dyn = out.Perception_DYN_OBJ_Out;
      const auto& lh = out.Perception_LH_Out;
      const auto& la = out.Perception_LA_Out;
      const bool log_it =
          (std::strcmp(mode, "freeze") != 0) || (out_seq - freeze_log_at >= 50);
      if (std::strcmp(mode, "freeze") == 0) {
        if (log_it) {
          freeze_log_at = out_seq;
        } else {
          ++out_seq;
          return;
        }
      }
      std::cout << "gf-perception-fcm: out#" << out_seq << " mode=" << mode
                << " vd=" << static_cast<int>(dyn.m_OBJ_VD_Count)
                << " ped=" << static_cast<int>(dyn.m_OBJ_Ped_Count)
                << " cipv=" << static_cast<int>(dyn.m_OBJ_VD_CIPV_ID)
                << " lh=" << static_cast<int>(lh.m_hostline_num)
                << " la=" << static_cast<int>(la.m_adj_line_num)
                << " lanes=" << static_cast<int>(truth.lane_count)
                << " ego_lane=" << static_cast<int>(truth.ego_lane_index_from_left);
      if (dyn.m_OBJ_VD_Count > 0) {
        std::cout << " lead=" << dyn.m_Obj_item[0].m_OBJ_Long_Distance
                  << " lat=" << dyn.m_Obj_item[0].m_OBJ_Lat_Distance
                  << " rel_v=" << dyn.m_Obj_item[0].m_OBJ_Relative_Long_Velocity;
      }
      if (in_frame) {
        std::cout << " in_frame=" << *in_frame;
      }
      std::cout << std::endl;
      ++out_seq;
    };

    if (frame_kind == gf_fcm::FrameSourceKind::None) {
      // Wave-A: prefer In/Ego stamp; if stalled, keepalive frozen Out (no clear).
      bool sent = false;
      if (in_ts.has_value()) {
        publish_out(*in_ts, in_frame ? *in_frame : static_cast<std::uint32_t>(out_seq));
        sent = true;
        last_keep_ns = gf_fcm::FrameSource::NowNs();
      }
      if (!sent) {
        auto ego_taken = ego_sub.Take();
        if (ego_taken && ego_taken.Value().has_value()) {
          const auto& ego = *ego_taken.Value();
          publish_out(ego.timestamp_ns, static_cast<std::uint32_t>(out_seq));
          sent = true;
          last_keep_ns = gf_fcm::FrameSource::NowNs();
        }
      }
      if (!sent) {
        const std::uint64_t now = gf_fcm::FrameSource::NowNs();
        if (last_keep_ns == 0 ||
            (now - last_keep_ns >=
             static_cast<std::uint64_t>(keep_ms) * 1000000ULL)) {
          last_keep_ns = now;
          publish_out(now, static_cast<std::uint32_t>(out_seq));
        }
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(20));
      continue;
    }

    // Frame camera mode: new frame → Out; no frame → keepalive freeze (no timeout clear).
    if (auto frame = frames.Poll()) {
      last_keep_ns = gf_fcm::FrameSource::NowNs();
      if (backend == gf_fcm::BackendKind::Onnx) {
        (void)gf_fcm::DetectOnnxOrHeuristic(*frame, model_path);
      } else {
        (void)gf_fcm::DetectStubFrame(*frame, out_seq);
      }
      const std::uint64_t ts =
          frame->meta.timestamp_ns != 0 ? frame->meta.timestamp_ns
                                        : (in_ts ? *in_ts : last_keep_ns);
      publish_out(ts, static_cast<std::uint32_t>(frame->meta.seq));
    } else {
      const std::uint64_t now = gf_fcm::FrameSource::NowNs();
      if (last_keep_ns == 0 ||
          (now - last_keep_ns >=
           static_cast<std::uint64_t>(keep_ms) * 1000000ULL)) {
        last_keep_ns = now;
        publish_out(in_ts ? *in_ts : now, static_cast<std::uint32_t>(out_seq));
      }
    }

    (void)ego_sub.Take();
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }
  return EXIT_SUCCESS;
}
