// perception.rcm — rear FOV truth → Perception_Rear_Out_St (FCM subset for LC).
// Requires EgoMotion (stale → silence). SIL truth: gf.channel.rcm_truth. No invent.

#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_ara/com/binding/iceoryx/wait_set.hpp"
#include "gf_ara/runtime/process_bringup.hpp"
#include "gf_gen/ego_motion.hpp"
#include "gf_gen/perception__rear__out__st.hpp"
#include "gf_channel/gf_channel.h"
#include "gf_channel/boundary_pods.h"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <optional>

namespace {

constexpr const char* kProcess = "perception.rcm";
constexpr const char* kTruthSlotDefault = "gf.channel.rcm_truth";
constexpr const char* kCamSlotDefault = "gf.channel.rear";
constexpr std::uint64_t kEgoStaleNs = 500000000ULL;
constexpr std::uint32_t kWaitSliceMs = 20;
constexpr std::uint64_t kIdEgo = 1;

const char* TruthSlot() {
  const char* v = std::getenv("GF_RCM_TRUTH_SLOT");
  if (v && v[0]) {
    return v;
  }
  return kTruthSlotDefault;
}

const char* CamSlot() {
  const char* v = std::getenv("GF_RCM_CAMERA_SLOT");
  if (v && v[0]) {
    return v;
  }
  v = std::getenv("GF_CAMERA_SLOT_REAR");
  if (v && v[0]) {
    return v;
  }
  return kCamSlotDefault;
}

std::uint64_t NowNs() {
  return static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(
          std::chrono::steady_clock::now().time_since_epoch())
          .count());
}

bool ReadRcmTruth(GfChannel* ch, std::uint64_t* last_seq, gf_gen::Perception_Rear_Out_St* out) {
  if (!ch || !out || !last_seq) {
    return false;
  }
  GfRcmTruthPod pod{};
  std::uint32_t got = 0;
  std::uint64_t ts = 0;
  std::uint32_t w = 0;
  std::uint32_t h = 0;
  std::uint16_t fmt = 0;
  const int n =
      gf_channel_latest(ch, &pod, sizeof(pod), &got, last_seq, &ts, &w, &h, &fmt);
  if (n <= 0 || got < sizeof(pod) || pod.magic != GF_CH_RCM_MAGIC ||
      pod.version != GF_CH_RCM_VERSION || !pod.valid) {
    return false;
  }
  out->timestamp_ns = pod.timestamp_ns ? pod.timestamp_ns : ts;
  out->valid = 1;
  out->n_lane = pod.n_lane > GF_CH_RCM_MAX_LANE ? GF_CH_RCM_MAX_LANE : pod.n_lane;
  out->n_obj = pod.n_obj > GF_CH_RCM_MAX_OBJ ? GF_CH_RCM_MAX_OBJ : pod.n_obj;
  for (std::uint8_t i = 0; i < out->n_lane; ++i) {
    out->lanes[i].c0_m = pod.lanes[i].c0_m;
    out->lanes[i].c1_rad = pod.lanes[i].c1_rad;
    out->lanes[i].c2 = pod.lanes[i].c2;
    out->lanes[i].c3 = pod.lanes[i].c3;
    out->lanes[i].view_range_m = pod.lanes[i].view_range_m;
    out->lanes[i].quality = pod.lanes[i].quality;
    out->lanes[i].side = pod.lanes[i].side;
  }
  for (std::uint8_t i = 0; i < out->n_obj; ++i) {
    out->objects[i].object_id = pod.objects[i].object_id;
    out->objects[i].object_class = pod.objects[i].object_class;
    out->objects[i].long_dist_m = pod.objects[i].long_dist_m;
    out->objects[i].lat_dist_m = pod.objects[i].lat_dist_m;
    out->objects[i].rel_vel_long_mps = pod.objects[i].rel_vel_long_mps;
    out->objects[i].rel_vel_lat_mps = pod.objects[i].rel_vel_lat_mps;
    out->objects[i].abs_vel_mps = pod.objects[i].abs_vel_mps;
  }
  return true;
}

void DrainEgo(gf_gen::EgoMotionProxy& ego_sub, std::optional<gf_gen::EgoMotion>* last_ego,
              std::uint64_t* last_ego_mono_ns) {
  for (;;) {
    auto t = ego_sub.Take();
    if (!t || !t.Value().has_value()) {
      break;
    }
    *last_ego = *t.Value();
    *last_ego_mono_ns = NowNs();
  }
}

}  // namespace

int main() {
  gf_ara::com::binding::iceoryx::InitRuntime("gf-perception-rcm");

  gf_ara::runtime::ProcessSupervisor supervisor;
  if (!supervisor.Start(kProcess)) {
    std::cerr << "[ERROR] perception.rcm: ProcessSupervisor.Start failed\n";
    return EXIT_FAILURE;
  }

  const char* truth_slot = TruthSlot();
  const char* cam_slot = CamSlot();
  GfChannel* truth = gf_channel_open(truth_slot);
  GfChannel* cam = gf_channel_open(cam_slot);
  gf_gen::EgoMotionProxy ego_sub{};
  gf_ara::com::binding::iceoryx::EventWaitSet<2> waitset;
  if (!waitset.AttachProxy(ego_sub, kIdEgo)) {
    std::cerr << "[ERROR] perception.rcm: Attach Ego WaitSet failed\n";
    return EXIT_FAILURE;
  }
  gf_gen::Perception_Rear_Out_StSkeleton out_pub{};

  std::optional<gf_gen::EgoMotion> last_ego;
  std::uint64_t last_ego_mono_ns = 0;
  std::uint64_t last_truth_seq = 0;
  std::uint64_t last_cam_seq = 0;

  std::cout << "gf-perception-rcm: truth=" << truth_slot
            << " channel=" << (truth ? "open" : "missing")
            << " cam=" << cam_slot << "/" << (cam ? "open" : "missing")
            << " EgoMotion=required (stale→silence; truth wait_seq; no private 50ms)\n";

  while (!iox::posix::hasTerminationRequested()) {
    supervisor.Tick();
    if (supervisor.ExitForEmRestart()) {
      return gf_ara::exec::kEmRestartExitCode;
    }

    DrainEgo(ego_sub, &last_ego, &last_ego_mono_ns);
    const bool ego_ok =
        last_ego.has_value() && (NowNs() - last_ego_mono_ns) <= kEgoStaleNs;

    if (!truth) {
      truth = gf_channel_open(truth_slot);
    }
    if (!cam) {
      cam = gf_channel_open(cam_slot);
    }
    if (cam) {
      std::uint8_t scratch[64]{};
      std::uint32_t got = 0;
      std::uint64_t ts = 0;
      std::uint32_t ww = 0;
      std::uint32_t hh = 0;
      std::uint16_t fmt = 0;
      (void)gf_channel_latest(cam, scratch, sizeof(scratch), &got, &last_cam_seq, &ts, &ww,
                              &hh, &fmt);
    }

    if (!ego_ok) {
      (void)waitset.TimedWaitMs(kWaitSliceMs);
      continue;
    }
    if (!truth) {
      (void)waitset.TimedWaitMs(kWaitSliceMs);
      continue;
    }

    const int woke = gf_channel_wait_seq(truth, last_truth_seq, kWaitSliceMs);
    DrainEgo(ego_sub, &last_ego, &last_ego_mono_ns);
    if (!(last_ego.has_value() && (NowNs() - last_ego_mono_ns) <= kEgoStaleNs)) {
      continue;
    }

    if (woke == 1) {
      gf_gen::Perception_Rear_Out_St out{};
      if (ReadRcmTruth(truth, &last_truth_seq, &out)) {
        if (!out.timestamp_ns) {
          out.timestamp_ns = last_ego->timestamp_ns;
        }
        (void)out_pub.Send(out);
      }
    }
  }
  waitset.MarkForDestruction();
  if (truth) {
    gf_channel_close(truth);
  }
  if (cam) {
    gf_channel_close(cam);
  }
  return EXIT_SUCCESS;
}
