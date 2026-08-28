#include "detect_backend.hpp"
#include "frame_source.hpp"

#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_ara/log/logger.hpp"
#include "gf_ara/runtime/process_bringup.hpp"
#include "gf_gen/proxy/perception__in__st_proxy.hpp"
#include "gf_gen/skeleton/perception_message__out__st_skeleton.hpp"

#if __has_include("gf_gen/frame_ingest_config.hpp")
#include "gf_gen/frame_ingest_config.hpp"
#define GF_FCM_HAS_FRAME_INGEST 1
#endif

#include "gf_channel/gf_channel.h"
#include "gf_channel/boundary_pods.h"
#include "gf_app/frame_watch.hpp"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <optional>
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

// 1 = every Out; N = on-change + every Nth (default 40 ≈ 2s at 20 Hz).
int LogEvery() {
  const char* v = std::getenv("GF_APP_LOG_EVERY");
  if (!v || !v[0]) {
    return 40;
  }
  const int n = std::atoi(v);
  return n < 1 ? 1 : n;
}

bool FMoved(float a, float b, float eps) { return std::fabs(a - b) > eps; }

const char* FrameSourceLabel() {
  const char* v = std::getenv("GF_FRAME_SOURCE");
  if (!v || !v[0]) {
    v = std::getenv("GF_ACTIVE_SOURCE");
  }
#if defined(GF_FCM_HAS_FRAME_INGEST)
  if (!v || !v[0]) {
    v = gf_gen::frame_ingest::kActiveSource;
  }
#endif
  return (v && v[0]) ? v : "none";
}

// colorbar/synth keep camera-clock + keepalive until that work is filled in.
bool ColorbarReserved() {
  const char* s = FrameSourceLabel();
  return std::strcmp(s, "colorbar") == 0 || std::strcmp(s, "synth") == 0;
}

const char* FakePercSlot() {
  const char* v = std::getenv("GF_FAKE_PERC_SLOT");
#if defined(GF_FCM_HAS_FRAME_INGEST)
  if (!v || !v[0]) {
    v = gf_gen::frame_ingest::kFakePercSlot;
  }
#endif
  return (v && v[0]) ? v : "gf.channel.fake_perc";
}

struct TruthSnapshot {
  float lead_distance_m{0.0f};
  float lead_rel_speed_mps{0.0f};
  float lead_lat_m{0.0f};
  float lead_heading_rad{0.0f};
  std::uint8_t lead_lane_assignment{3};
  std::uint64_t timestamp_ns{0};
  std::uint64_t seq{0};
  bool lead_valid{false};
  bool file_ok{false};  // channel payload valid (name kept for FillOut callers)
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
  std::uint8_t lane_avail{2};
  float lane_conf{0.95f};
  float lane_vr_end_m{130.0f};
};

TruthSnapshot FromFakePercPod(const GfFakePercPod& p) {
  TruthSnapshot t{};
  if (p.magic != GF_CH_FAKE_PERC_MAGIC || p.version != GF_CH_POD_VERSION || !p.valid) {
    return t;
  }
  t.file_ok = true;
  t.timestamp_ns = p.timestamp_ns;
  t.seq = p.seq;
  t.lead_valid = p.lead_valid != 0;
  t.lead_distance_m = p.lead_distance_m;
  t.lead_rel_speed_mps = p.lead_rel_speed_mps;
  t.lead_lat_m = p.lead_lat_m;
  t.lead_heading_rad = p.lead_heading_rad;
  t.lead_lane_assignment = p.lead_lane_assignment;
  t.lane_count = p.lane_count;
  t.ego_lane_index_from_left = p.ego_lane_index_from_left;
  t.lane_width_m = p.lane_width_m;
  t.host_left_c0 = p.host_left_c0;
  t.host_right_c0 = p.host_right_c0;
  t.host_c1 = p.host_c1;
  t.host_c2 = p.host_c2;
  t.host_left_c1 = p.host_left_c1;
  t.host_right_c1 = p.host_right_c1;
  t.host_left_c2 = p.host_left_c2;
  t.host_right_c2 = p.host_right_c2;
  t.host_left_type = p.host_left_type;
  t.host_right_type = p.host_right_type;
  t.adj_n = p.adj_n;
  for (int i = 0; i < 4; ++i) {
    t.adj_side[i] = p.adj_side[i];
    t.adj_c0[i] = p.adj_c0[i];
    t.adj_c1[i] = p.adj_c1[i];
    t.adj_c2[i] = p.adj_c2[i];
    t.adj_type[i] = p.adj_type[i];
  }
  t.dyn_n = p.dyn_n;
  t.vd_count = p.vd_count;
  t.ped_count = p.ped_count;
  t.cipv_id = p.cipv_id;
  const int n = std::min<int>(p.dyn_n, 13);
  for (int i = 0; i < n; ++i) {
    t.obj_id[i] = p.obj[i].id;
    t.obj_class[i] = p.obj[i].cls;
    t.obj_long[i] = p.obj[i].long_m;
    t.obj_lat[i] = p.obj[i].lat_m;
    t.obj_heading[i] = p.obj[i].heading_rad;
    t.obj_len[i] = p.obj[i].len_m;
    t.obj_wid[i] = p.obj[i].wid_m;
    t.obj_rel_v[i] = p.obj[i].rel_v_mps;
    t.obj_assign[i] = p.obj[i].assign;
    t.obj_ped[i] = p.obj[i].is_ped;
  }
  t.lane_avail = p.lane_avail;
  t.lane_conf = p.lane_conf;
  t.lane_vr_end_m = p.lane_vr_end_m;
  return t;
}

TruthSnapshot ReadFakePerc(GfChannel* ch, std::uint64_t* last_seq) {
  TruthSnapshot t{};
  if (!ch) {
    return t;
  }
  GfFakePercPod pod{};
  std::uint32_t got = 0;
  std::uint64_t ts = 0;
  std::uint32_t w = 0;
  std::uint32_t h = 0;
  std::uint16_t fmt = 0;
  const int r =
      gf_channel_latest(ch, &pod, sizeof(pod), &got, last_seq, &ts, &w, &h, &fmt);
  if (r != 1 || got < sizeof(GfFakePercPod)) {
    return t;
  }
  return FromFakePercPod(pod);
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
    case gf_fcm::FrameSourceKind::CameraShm:
      return "camera_shm";
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
  const bool colorbar_reserved = ColorbarReserved();
  // colorbar/synth only: keep Out keepalive. Other sources: PHM alive, no freeze Send.
  const std::uint32_t keep_ms = EnvU32("GF_OUT_KEEPALIVE_MS", 50);
  const char* model_env = std::getenv("GF_ONNX_MODEL");
  const std::string model_path = (model_env && model_env[0]) ? model_env : "";

  gf_fcm::FrameSource frames(frame_kind);
  gf_gen::Perception_In_StProxy in_sub{};
  gf_gen::Perception_MESSAGE_Out_StSkeleton out_pub{};

  GfChannel* fake_ch = nullptr;
  std::uint64_t fake_seq = 0;
  float last_in_speed = -1.0f;
  std::optional<std::uint32_t> last_in_frame;
  std::optional<std::uint64_t> last_in_ts;

  std::uint64_t out_seq = 0;
  std::uint64_t last_keep_ns = 0;
  std::uint32_t last_image_frame_id = 0;
  gf_gen::Perception_MESSAGE_Out_St last_out{};
  bool have_frozen = false;
  std::uint64_t last_truth_seq = 0;
  std::uint64_t last_truth_ts = 0;
  int last_truth_lanes = 0;
  int last_truth_ego_lane = 0;
  const int log_every = LogEvery();
  gf_app::EnsureDiagLogSinks();
  gf_app::FrameWatch rx_fake;
  gf_app::FrameWatch rx_in;
  gf_app::FrameWatch tx_out;
  rx_fake.Init("fcm", "rx.fake_perc");
  rx_fake.BindChannel("fake_perc");
  rx_in.Init("fcm", "rx.perc_in");
  rx_in.BindService("Perception_In_St");
  tx_out.Init("fcm", "tx.out");
  tx_out.BindService("Perception_MESSAGE_Out_St");
  tx_out.BindCameraCeiling();
  const char* last_log_mode = "";
  int last_log_vd = -1;
  int last_log_cipv = -1;
  int last_log_lh = -1;
  int last_log_lanes = -1;
  int last_log_ego_lane = -1;
  float last_log_lead = 0.0f;
  float last_log_lat = 0.0f;
  float last_log_rel_v = 0.0f;
  float last_log_speed = -1.0f;
  bool last_log_had_lead = false;

  std::cout << "gf-perception-fcm: start frame_source=" << FrameSourceLabel()
            << " kind=" << KindName(frame_kind)
            << " backend="
            << (backend == gf_fcm::BackendKind::Onnx ? "onnx" : "stub")
            << " fake_perc=" << FakePercSlot()
            << " (SIL fake_perc via GfChannel; FCM algo not production)";
  if (colorbar_reserved) {
    std::cout << " out=on-change keepalive_ms=" << keep_ms << " (colorbar reserved)";
  } else {
    std::cout << " out=on-change (no freeze keepalive)";
  }
  std::cout << " stdout=on-change+/" << log_every
            << " m_frame_id=camera-only out_seq=update-only"
            << " frame_watch=identity+budget"
            << " out[" << tx_out.PolicyHint() << "]"
            << " in[" << rx_in.PolicyHint() << "]" << std::endl;

  while (!iox::posix::hasTerminationRequested()) {
    supervisor.Tick();
    if (supervisor.ExitForEmRestart()) {
      return gf_ara::exec::kEmRestartExitCode;
    }

    if (!fake_ch) {
      fake_ch = gf_channel_open(FakePercSlot());
    }

    {
      auto taken = in_sub.Take();
      if (taken && taken.Value().has_value()) {
        last_in_frame = taken.Value()->ipc_frame_counter;
        last_in_ts = taken.Value()->timestamp_ns;
        last_in_speed = taken.Value()->vehicle_speed;
        rx_in.Observe(*last_in_frame, *last_in_ts);
      }
    }

    const TruthSnapshot truth = ReadFakePerc(fake_ch, &fake_seq);
    if (truth.file_ok) {
      rx_fake.Observe(truth.seq, truth.timestamp_ns);
    }
    const bool truth_fresh =
        truth.file_ok &&
        (truth.seq != last_truth_seq || truth.timestamp_ns != last_truth_ts ||
         (!have_frozen &&
          (truth.lead_valid || truth.lane_count > 0 || truth.dyn_n > 0)));

    auto publish_out = [&](std::uint64_t ts, std::uint32_t image_frame_id) {
      // image_frame_id: camera ingest seq only. No camera → 0.
      if (!truth_fresh && last_in_ts && *last_in_ts > 0) {
        ts = *last_in_ts;
      }
      gf_gen::Perception_MESSAGE_Out_St out{};
      const char* mode = "update";
      if (truth_fresh) {
        FillOutFromTruth(out, truth, ts, image_frame_id);
        last_out = out;
        have_frozen = true;
        last_truth_seq = truth.seq;
        last_truth_ts = truth.timestamp_ns;
        last_truth_lanes = static_cast<int>(truth.lane_count);
        last_truth_ego_lane = static_cast<int>(truth.ego_lane_index_from_left);
      } else if (have_frozen && colorbar_reserved) {
        out = last_out;
        out.Perception_DYN_OBJ_Out.m_time_stamp = ts / 1000ULL;
        out.Perception_LH_Out.m_time_stamp = ts / 1000ULL;
        out.Perception_LA_Out.m_time_stamp = ts / 1000ULL;
        mode = "freeze";
      } else if (colorbar_reserved) {
        FillOutFromTruth(out, TruthSnapshot{}, ts, 0);
        mode = "idle";
      } else {
        gf_ara::log::Logger::Instance().Error(
            "fcm", "tx.out rejected freeze/idle copy (not a new perception sample)");
        return;
      }
      if (!static_cast<bool>(out_pub.Send(out))) {
        return;
      }
      if (std::strcmp(mode, "update") == 0) {
        ++out_seq;
        tx_out.Observe(out_seq, ts);
      }
      const auto& dyn = out.Perception_DYN_OBJ_Out;
      const auto& lh = out.Perception_LH_Out;
      const auto& la = out.Perception_LA_Out;
      const int vd = static_cast<int>(dyn.m_OBJ_VD_Count);
      const int cipv = static_cast<int>(dyn.m_OBJ_VD_CIPV_ID);
      const int lh_n = static_cast<int>(lh.m_hostline_num);
      const int lanes = (std::strcmp(mode, "update") == 0)
                            ? static_cast<int>(truth.lane_count)
                            : last_truth_lanes;
      const int ego_lane = (std::strcmp(mode, "update") == 0)
                               ? static_cast<int>(truth.ego_lane_index_from_left)
                               : last_truth_ego_lane;
      const bool had_lead = vd > 0;
      const float lead = had_lead ? dyn.m_Obj_item[0].m_OBJ_Long_Distance : 0.0f;
      const float lat = had_lead ? dyn.m_Obj_item[0].m_OBJ_Lat_Distance : 0.0f;
      const float rel_v =
          had_lead ? dyn.m_Obj_item[0].m_OBJ_Relative_Long_Velocity : 0.0f;
      const bool changed =
          std::strcmp(mode, last_log_mode) != 0 || vd != last_log_vd ||
          cipv != last_log_cipv || lh_n != last_log_lh || lanes != last_log_lanes ||
          ego_lane != last_log_ego_lane || had_lead != last_log_had_lead ||
          (had_lead && (FMoved(lead, last_log_lead, 0.5f) ||
                        FMoved(lat, last_log_lat, 0.5f) ||
                        FMoved(rel_v, last_log_rel_v, 0.2f))) ||
          (last_in_speed >= 0.0f && FMoved(last_in_speed, last_log_speed, 0.2f));
      if (log_every <= 1 || changed ||
          (out_seq % static_cast<std::uint64_t>(log_every) == 0)) {
        std::cout << "gf-perception-fcm: out#" << out_seq << " mode=" << mode
                  << " vd=" << vd << " ped=" << static_cast<int>(dyn.m_OBJ_Ped_Count)
                  << " cipv=" << cipv << " lh=" << lh_n
                  << " la=" << static_cast<int>(la.m_adj_line_num)
                  << " lanes=" << lanes << " ego_lane=" << ego_lane;
        if (had_lead) {
          std::cout << " lead=" << lead << " lat=" << lat << " rel_v=" << rel_v;
        }
        if (last_in_frame) {
          std::cout << " in_frame=" << *last_in_frame;
        }
        if (last_in_speed >= 0.0f) {
          std::cout << " in_speed=" << last_in_speed;
        }
        std::cout << std::endl;
        last_log_mode = mode;
        last_log_vd = vd;
        last_log_cipv = cipv;
        last_log_lh = lh_n;
        last_log_lanes = lanes;
        last_log_ego_lane = ego_lane;
        last_log_had_lead = had_lead;
        last_log_lead = lead;
        last_log_lat = lat;
        last_log_rel_v = rel_v;
        last_log_speed = last_in_speed;
      }
    };

    const auto keep_due = [&]() {
      const std::uint64_t now = gf_fcm::FrameSource::NowNs();
      return last_keep_ns == 0 ||
             (now - last_keep_ns >=
              static_cast<std::uint64_t>(keep_ms) * 1000000ULL);
    };

    if (!colorbar_reserved) {
      if (frame_kind != gf_fcm::FrameSourceKind::None) {
        if (auto frame = frames.Poll()) {
          if (backend == gf_fcm::BackendKind::Onnx) {
            (void)gf_fcm::DetectOnnxOrHeuristic(*frame, model_path);
          } else {
            (void)gf_fcm::DetectStubFrame(*frame, out_seq);
          }
          last_image_frame_id = static_cast<std::uint32_t>(frame->meta.seq);
        }
      }
      if (truth_fresh) {
        const std::uint64_t ts =
            truth.timestamp_ns ? truth.timestamp_ns
                               : (last_in_ts && *last_in_ts > 0
                                      ? *last_in_ts
                                      : gf_fcm::FrameSource::NowNs());
        const std::uint32_t img =
            (frame_kind == gf_fcm::FrameSourceKind::None) ? 0u : last_image_frame_id;
        publish_out(ts, img);
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
      continue;
    }

    // colorbar/synth reserved: camera clock + keepalive unchanged.
    if (frame_kind == gf_fcm::FrameSourceKind::None) {
      if (truth_fresh) {
        const std::uint64_t ts =
            truth.timestamp_ns ? truth.timestamp_ns
                               : (last_in_ts && *last_in_ts > 0
                                      ? *last_in_ts
                                      : gf_fcm::FrameSource::NowNs());
        publish_out(ts, 0);
        last_keep_ns = gf_fcm::FrameSource::NowNs();
      } else if (have_frozen && keep_due()) {
        last_keep_ns = gf_fcm::FrameSource::NowNs();
        publish_out(last_keep_ns, 0);
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
      continue;
    }

    if (auto frame = frames.Poll()) {
      last_keep_ns = gf_fcm::FrameSource::NowNs();
      if (backend == gf_fcm::BackendKind::Onnx) {
        (void)gf_fcm::DetectOnnxOrHeuristic(*frame, model_path);
      } else {
        (void)gf_fcm::DetectStubFrame(*frame, out_seq);
      }
      const std::uint64_t ts =
          frame->meta.timestamp_ns != 0
              ? frame->meta.timestamp_ns
              : (last_in_ts && *last_in_ts > 0 ? *last_in_ts : last_keep_ns);
      publish_out(ts, static_cast<std::uint32_t>(frame->meta.seq));
    } else if (truth_fresh) {
      const std::uint64_t ts =
          truth.timestamp_ns ? truth.timestamp_ns : gf_fcm::FrameSource::NowNs();
      publish_out(ts, 0);
      last_keep_ns = gf_fcm::FrameSource::NowNs();
    } else if (have_frozen && keep_due()) {
      last_keep_ns = gf_fcm::FrameSource::NowNs();
      publish_out(last_keep_ns, 0);
    }

    std::this_thread::sleep_for(std::chrono::milliseconds(1));
  }
  if (fake_ch) {
    gf_channel_close(fake_ch);
  }
  return EXIT_SUCCESS;
}
