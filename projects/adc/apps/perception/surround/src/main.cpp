#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_ara/runtime/process_bringup.hpp"
#include "gf_gen/skeleton/surround_world_skeleton.hpp"
#include "gf_gen/skeleton/freespace_near_skeleton.hpp"
#include "gf_channel/gf_channel.h"
#include "gf_channel/boundary_pods.h"
#include "freespace_near.hpp"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <thread>

namespace {
constexpr const char* kProcess = "perception.surround";
constexpr const char* kSlot = "gf.channel.surround_world";

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
  if (n <= 0 || got < sizeof(pod) || pod.magic != GF_CH_SURROUND_MAGIC ||
      pod.version != GF_CH_SURROUND_VERSION || !pod.valid) {
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
  }
  gf_gen::FreespaceNear fs{};
  gf_surround::ComputeFreespaceNear(samples, n, out.timestamp_ns, &fs);
  (void)fs_skel.Send(fs);
}

}  // namespace

int main() {
  gf_ara::com::binding::iceoryx::InitRuntime("gf-perception-surround");

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

  gf_gen::SurroundWorldSkeleton world;
  gf_gen::FreespaceNearSkeleton fs_skel;
  std::uint64_t last_seq = 0;
  std::cout << "gf-perception-surround: slot=" << slot
            << " channel=" << (ch ? "open" : "missing")
            << " (no SIL invent; publish only on valid pod)\n";

  while (!iox::posix::hasTerminationRequested()) {
    supervisor.Tick();
    if (supervisor.ExitForEmRestart()) {
      return gf_ara::exec::kEmRestartExitCode;
    }
    if (!ch) {
      ch = gf_channel_open(slot);
    }
    gf_gen::SurroundWorld out{};
    // Prefer silence over invented objects/slots.
    if (ReadSurroundPod(ch, &last_seq, &out)) {
      PublishWorldAndFs(world, fs_skel, out);
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
  }
  if (ch) {
    gf_channel_close(ch);
  }
  return 0;
}
