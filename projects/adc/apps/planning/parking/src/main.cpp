#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_ara/runtime/process_bringup.hpp"
#include "gf_gen/proxy/surround_world_proxy.hpp"
#include "gf_gen/skeleton/parking_trajectory_skeleton.hpp"

#include "m_park_tick.hpp"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <thread>

namespace {
constexpr const char* kProcess = "planning.parking";
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
  gf_gen::ParkingTrajectorySkeleton traj;

  while (!iox::posix::hasTerminationRequested()) {
    supervisor.Tick();
    if (supervisor.ExitForEmRestart()) {
      return gf_ara::exec::kEmRestartExitCode;
    }

    float sx = 6.0f, sy = -3.2f, syaw = 0.0f, slen = 5.0f, swid = 2.4f;
    bool free = false;
    if (auto st = surround.Take(); st.HasValue() && st.Value().has_value()) {
      const auto& w = *st.Value();
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

    gf_gen::ParkingTrajectory out{};
    out.timestamp_ns = static_cast<uint64_t>(
        std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now().time_since_epoch())
            .count());
    out.valid = 0;
    out.n_points = 0;

    const auto tick = oct_gen::m_park_tick(sx, sy, syaw, slen, swid, free, /*confirmed=*/1);
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
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
  }
  return 0;
}
