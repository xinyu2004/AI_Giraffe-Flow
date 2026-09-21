#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_ara/com/binding/iceoryx/wait_set.hpp"
#include "gf_ara/runtime/process_bringup.hpp"
#include "gf_gen/proxy/surround_world_proxy.hpp"
#include "gf_gen/proxy/freespace_near_proxy.hpp"
#include "gf_gen/skeleton/parking_trajectory_skeleton.hpp"

#include "m_park_tick.hpp"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <optional>

namespace {
constexpr const char* kProcess = "planning.parking";
constexpr std::uint32_t kWaitSliceMs = 20;
constexpr std::uint64_t kIdSurround = 1;
constexpr std::uint64_t kIdNear = 2;
}

int main() {
  gf_ara::com::binding::iceoryx::InitRuntime("gf-planning-parking");

  gf_ara::runtime::ProcessSupervisor supervisor;
  if (!supervisor.Start(kProcess)) {
    std::cerr << "[ERROR] planning.parking: ProcessSupervisor.Start failed\n";
    return EXIT_FAILURE;
  }

  // Process only runs while DriveParkFG=ParkingActive (EM set-difference).
  gf_gen::SurroundWorldProxy surround;
  gf_gen::FreespaceNearProxy fs_near;
  gf_gen::ParkingTrajectorySkeleton traj;
  std::optional<gf_gen::FreespaceNear> last_fs;
  std::optional<gf_gen::SurroundWorld> last_world;
  bool surround_edge = false;
  bool near_edge = false;

  gf_ara::com::binding::iceoryx::EventWaitSet<4> waitset;
  if (!waitset.AttachProxy(surround, kIdSurround) || !waitset.AttachProxy(fs_near, kIdNear)) {
    std::cerr << "[ERROR] planning.parking: EventWaitSet attach failed\n";
    return EXIT_FAILURE;
  }

  std::cout << "gf-planning-parking: start (m_park_tick; on_change Send; EventWaitSet)\n";

  while (!iox::posix::hasTerminationRequested()) {
    supervisor.Tick();
    if (supervisor.ExitForEmRestart()) {
      return gf_ara::exec::kEmRestartExitCode;
    }

    (void)waitset.TimedWaitMs(kWaitSliceMs);

    for (;;) {
      auto t = fs_near.Take();
      if (!t.HasValue() || !t.Value().has_value()) {
        break;
      }
      last_fs = *t.Value();
      near_edge = true;
    }
    for (;;) {
      auto st = surround.Take();
      if (!st.HasValue() || !st.Value().has_value()) {
        break;
      }
      last_world = *st.Value();
      surround_edge = true;
    }

    if (!surround_edge && !near_edge) {
      continue;
    }
    surround_edge = near_edge = false;

    float sx = 6.0f, sy = -3.2f, syaw = 0.0f, slen = 5.0f, swid = 2.4f;
    bool free = false;
    std::uint64_t ts_ns = 0;
    if (last_world) {
      const auto& w = *last_world;
      ts_ns = w.timestamp_ns;
      for (std::uint8_t i = 0; i < w.n_slot; ++i) {
        if (w.slots[i].free) {
          sx = w.slots[i].center_x_m;
          sy = w.slots[i].center_y_m;
          syaw = w.slots[i].yaw_rad;
          slen = w.slots[i].length_m;
          swid = w.slots[i].width_m;
          free = true;
          break;
        }
      }
    }
    if (!ts_ns && last_fs) {
      ts_ns = last_fs->timestamp_ns;
    }
    if (!ts_ns) {
      ts_ns = static_cast<uint64_t>(
          std::chrono::duration_cast<std::chrono::nanoseconds>(
              std::chrono::steady_clock::now().time_since_epoch())
              .count());
    }
    // on_change identity: never reuse the previous publish timestamp.
    static std::uint64_t last_pub_ts = 0;
    if (ts_ns <= last_pub_ts) {
      ts_ns = last_pub_ts + 1;
    }
    last_pub_ts = ts_ns;

    gf_gen::ParkingTrajectory out{};
    out.timestamp_ns = ts_ns;
    out.valid = 0;
    out.n_points = 0;

    const float* d_r = nullptr;
    if (last_fs && last_fs->valid) {
      d_r = last_fs->d_r_m;
    }
    const auto tick =
        oct_gen::m_park_tick(sx, sy, syaw, slen, swid, free, /*confirmed=*/1, d_r);
    if (tick.valid && tick.n > 0) {
      out.valid = 1;
      out.n_points = std::min<std::uint8_t>(tick.n, 32);
      for (std::uint8_t i = 0; i < out.n_points; ++i) {
        out.x_m[i] = tick.x[i];
        out.y_m[i] = tick.y[i];
        out.yaw_rad[i] = tick.yaw[i];
      }
    }
    (void)traj.Send(out);
  }
  waitset.MarkForDestruction();
  return 0;
}
