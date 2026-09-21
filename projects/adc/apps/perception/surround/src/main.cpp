#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_ara/com/binding/iceoryx/wait_set.hpp"
#include "gf_ara/runtime/process_bringup.hpp"
#include "gf_gen/proxy/ego_motion_proxy.hpp"
#include "gf_gen/skeleton/surround_world_skeleton.hpp"
#include "gf_gen/skeleton/freespace_near_skeleton.hpp"
#include "gf_channel/gf_channel.h"
#include "gf_channel/boundary_pods.h"
#include "freespace_near.hpp"
#include "fs_envelope/fs_mounts.hpp"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <optional>

namespace {
constexpr const char* kProcess = "perception.surround";
constexpr const char* kSlot = "gf.channel.surround_world";
constexpr std::uint64_t kEgoStaleNs = 500000000ULL;  // 500 ms
/** Supervisor / open-retry cadence only — not an on_change publish clock. */
constexpr std::uint32_t kWaitSliceMs = 20;
constexpr std::uint64_t kIdEgo = 1;

bool ReadSurroundPod(GfChannel* ch, std::uint64_t* last_seq, gf_gen::SurroundWorld* out) {
  if (!ch || !out || !last_seq) {
    return false;
  }
  GfSurroundWorldPod pod{};
  std::uint32_t got = 0;
  std::uint64_t ts = 0;
  std::uint32_t w = 0;
  std::uint32_t h = 0;
  std::uint16_t fmt = 0;
  const int n =
      gf_channel_latest(ch, &pod, sizeof(pod), &got, last_seq, &ts, &w, &h, &fmt);
  static int s_drop_log = 0;
  if (n <= 0 || got < sizeof(pod) || pod.magic != GF_CH_SURROUND_MAGIC ||
      pod.version != GF_CH_SURROUND_VERSION || !pod.valid) {
    if (((++s_drop_log) % 50) == 1) {
      std::cerr << "[surround][pod] DROP n=" << n << " got=" << got
                << " need=" << sizeof(pod) << " magic=0x" << std::hex
                << (got >= 4 ? pod.magic : 0u) << std::dec
                << " ver=" << (got >= 6 ? pod.version : 0)
                << " expect_ver=" << GF_CH_SURROUND_VERSION << " valid="
                << (got >= 28 ? static_cast<int>(pod.valid) : -1) << "\n";
    }
    return false;
  }
  out->timestamp_ns = pod.timestamp_ns ? pod.timestamp_ns : ts;
  out->n_obj = pod.n_obj > 16 ? 16 : pod.n_obj;
  out->n_slot = pod.n_slot > 8 ? 8 : pod.n_slot;
  for (std::uint8_t i = 0; i < out->n_obj; ++i) {
    out->objects[i].object_id = pod.objects[i].object_id;
    out->objects[i].object_class = pod.objects[i].object_class;
    out->objects[i].long_dist_m = pod.objects[i].long_dist_m;
    out->objects[i].lat_dist_m = pod.objects[i].lat_dist_m;
    out->objects[i].rel_vel_long_mps = pod.objects[i].rel_vel_long_mps;
    out->objects[i].length_m = pod.objects[i].length_m;
    out->objects[i].width_m = pod.objects[i].width_m;
    out->objects[i].heading_rad = pod.objects[i].heading_rad;
  }
  for (std::uint8_t i = 0; i < out->n_slot; ++i) {
    out->slots[i].slot_id = pod.slots[i].slot_id;
    out->slots[i].center_x_m = pod.slots[i].center_x_m;
    out->slots[i].center_y_m = pod.slots[i].center_y_m;
    out->slots[i].yaw_rad = pod.slots[i].yaw_rad;
    out->slots[i].length_m = pod.slots[i].length_m;
    out->slots[i].width_m = pod.slots[i].width_m;
    out->slots[i].free = pod.slots[i].free;
  }
  return true;
}

void PublishWorldAndFs(gf_gen::SurroundWorldSkeleton& world,
                       gf_gen::FreespaceNearSkeleton& fs_skel,
                       const gf_gen::SurroundWorld& out) {
  (void)world.Send(out);
  gf_surround::ObjSample samples[16]{};
  const int n = out.n_obj > 16 ? 16 : static_cast<int>(out.n_obj);
  for (int i = 0; i < n; ++i) {
    samples[i].long_dist_m = out.objects[i].long_dist_m;
    samples[i].lat_dist_m = out.objects[i].lat_dist_m;
    if (out.objects[i].length_m > 0.5f) {
      samples[i].half_l_m = 0.5f * out.objects[i].length_m;
    }
    if (out.objects[i].width_m > 0.5f) {
      samples[i].half_w_m = 0.5f * out.objects[i].width_m;
    }
  }
  gf_gen::FreespaceNear fs{};
  gf_surround::ComputeFreespaceNear(samples, n, out.timestamp_ns, &fs);
  (void)fs_skel.Send(fs);
}

std::uint64_t NowNs() {
  return static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(
          std::chrono::steady_clock::now().time_since_epoch())
          .count());
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
  gf_ara::com::binding::iceoryx::InitRuntime("gf-perception-surround");

  gf_fs_envelope::InitEnvelopeFromMounts();
  std::cout << "gf-perception-surround: mounts side_lat=" << gf_fs_envelope::SideLatM()
            << " rear_cap=" << gf_fs_envelope::RearCapM()
            << " pod_ver=" << GF_CH_SURROUND_VERSION
            << " pod_sizeof=" << sizeof(GfSurroundWorldPod) << "\n";

  gf_ara::runtime::ProcessSupervisor supervisor;
  if (!supervisor.Start(kProcess)) {
    std::cerr << "[ERROR] perception.surround: ProcessSupervisor.Start failed\n";
    return EXIT_FAILURE;
  }

  const char* slot = std::getenv("GF_SURROUND_SLOT");
  if (!slot || !slot[0]) {
    slot = kSlot;
  }
  GfChannel* ch = gf_channel_open(slot);

  gf_gen::EgoMotionProxy ego_sub{};
  gf_ara::com::binding::iceoryx::EventWaitSet<2> waitset;
  if (!waitset.AttachProxy(ego_sub, kIdEgo)) {
    std::cerr << "[ERROR] perception.surround: Attach Ego WaitSet failed\n";
    return EXIT_FAILURE;
  }

  gf_gen::SurroundWorldSkeleton world;
  gf_gen::FreespaceNearSkeleton fs_skel;
  std::uint64_t last_seq = 0;
  std::optional<gf_gen::EgoMotion> last_ego;
  std::uint64_t last_ego_mono_ns = 0;
  std::cout << "gf-perception-surround: slot=" << slot
            << " channel=" << (ch ? "open" : "missing")
            << " EgoMotion=required (stale→silence; channel wait_seq; no private 50ms)\n";

  while (!iox::posix::hasTerminationRequested()) {
    supervisor.Tick();
    if (supervisor.ExitForEmRestart()) {
      return gf_ara::exec::kEmRestartExitCode;
    }

    DrainEgo(ego_sub, &last_ego, &last_ego_mono_ns);
    const bool ego_ok =
        last_ego.has_value() && (NowNs() - last_ego_mono_ns) <= kEgoStaleNs;
    if (!ego_ok) {
      (void)waitset.TimedWaitMs(kWaitSliceMs);
      continue;
    }

    if (!ch) {
      ch = gf_channel_open(slot);
      if (!ch) {
        (void)waitset.TimedWaitMs(kWaitSliceMs);
        continue;
      }
    }

    const int woke = gf_channel_wait_seq(ch, last_seq, kWaitSliceMs);
    DrainEgo(ego_sub, &last_ego, &last_ego_mono_ns);
    if (!(last_ego.has_value() && (NowNs() - last_ego_mono_ns) <= kEgoStaleNs)) {
      continue;
    }

    if (woke == 1) {
      gf_gen::SurroundWorld out{};
      if (ReadSurroundPod(ch, &last_seq, &out)) {
        if (!out.timestamp_ns) {
          out.timestamp_ns = last_ego->timestamp_ns;
        }
        PublishWorldAndFs(world, fs_skel, out);
      }
    }
  }
  waitset.MarkForDestruction();
  if (ch) {
    gf_channel_close(ch);
  }
  return 0;
}
