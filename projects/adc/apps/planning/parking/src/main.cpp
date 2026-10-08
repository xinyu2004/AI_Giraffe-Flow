#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_ara/com/binding/iceoryx/wait_set.hpp"
#include "gf_ara/runtime/process_bringup.hpp"
#include "gf_gen/surround_world.hpp"
#include "gf_gen/freespace_near.hpp"
#include "gf_gen/parking_slot.hpp"
#include "gf_gen/parking_trajectory.hpp"

#include "m_park_tick.hpp"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <optional>

namespace {
constexpr const char* kProcess = "planning.parking";
constexpr std::uint32_t kWaitSliceMs = 20;
constexpr std::uint64_t kIdSurround = 1;
constexpr std::uint64_t kIdNear = 2;
constexpr std::uint64_t kIdSlot = 3;

bool SlotFromP(const float p[6], float* x, float* y, float* yaw, float* len, float* wid) {
  const float ax = p[0];
  const float ay = p[1];
  const float bx = p[2];
  const float by = p[3];
  const float cx = p[4];
  const float cy = p[5];
  if (std::fabs(ax) + std::fabs(ay) + std::fabs(bx) + std::fabs(by) + std::fabs(cx) +
          std::fabs(cy) <
      1e-3f) {
    return false;
  }
  *x = 0.5f * (ax + cx);
  *y = 0.5f * (ay + cy);
  *len = std::hypot(bx - ax, by - ay);
  *wid = std::hypot(cx - bx, cy - by);
  *yaw = std::atan2(by - ay, bx - ax);
  return *len > 0.3f && *wid > 0.3f;
}

}  // namespace

int main() {
  gf_ara::com::binding::iceoryx::InitRuntime("gf-planning-parking");

  gf_ara::runtime::ProcessSupervisor supervisor;
  if (!supervisor.Start(kProcess)) {
    std::cerr << "[ERROR] planning.parking: ProcessSupervisor.Start failed\n";
    return EXIT_FAILURE;
  }

  gf_gen::SurroundWorldProxy surround;
  gf_gen::FreespaceNearProxy fs_near;
  gf_gen::ParkingSlotProxy slot;
  gf_gen::ParkingTrajectorySkeleton traj;
  std::optional<gf_gen::FreespaceNear> last_fs;
  std::optional<gf_gen::SurroundWorld> last_world;
  std::optional<gf_gen::ParkingSlot> last_slot;
  bool surround_edge = false;
  bool near_edge = false;
  bool slot_edge = false;

  gf_ara::com::binding::iceoryx::EventWaitSet<4> waitset;
  if (!waitset.AttachProxy(surround, kIdSurround) || !waitset.AttachProxy(fs_near, kIdNear) ||
      !waitset.AttachProxy(slot, kIdSlot)) {
    std::cerr << "[ERROR] planning.parking: EventWaitSet attach failed\n";
    return EXIT_FAILURE;
  }

  std::cout << "gf-planning-parking: start (m_park_tick; ParkingSlot P*+confirmed)\n";

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
    for (;;) {
      auto sl = slot.Take();
      if (!sl.HasValue() || !sl.Value().has_value()) {
        break;
      }
      last_slot = *sl.Value();
      slot_edge = true;
    }

    if (!surround_edge && !near_edge && !slot_edge) {
      continue;
    }
    surround_edge = near_edge = slot_edge = false;

    float sx = 0.0f, sy = 0.0f, syaw = 0.0f, slen = 0.0f, swid = 0.0f;
    bool have_p = false;
    bool confirmed = false;
    std::uint64_t ts_ns = 0;
    if (last_slot) {
      ts_ns = last_slot->timestamp_ns;
      confirmed = last_slot->uiAPAStatus != 0;
      const float p[6] = {
          last_slot->fParkingSlot_P0X, last_slot->fParkingSlot_P0Y,
          last_slot->fParkingSlot_P1X, last_slot->fParkingSlot_P1Y,
          last_slot->fParkingSlot_P2X, last_slot->fParkingSlot_P2Y,
      };
      have_p = SlotFromP(p, &sx, &sy, &syaw, &slen, &swid);
    }
    bool free = have_p;
    if (have_p && last_world) {
      float best = 1.0e9f;
      for (std::uint8_t i = 0; i < last_world->n_slot && i < 6; ++i) {
        const auto& s = last_world->slots[i];
        const float d = std::hypot(s.center_x_m - sx, s.center_y_m - sy);
        if (d < best) {
          best = d;
          free = s.free != 0;
        }
      }
    }
    if (last_world && !ts_ns) {
      ts_ns = last_world->timestamp_ns;
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
    if (have_p) {
      const auto tick =
          oct_gen::m_park_tick(sx, sy, syaw, slen, swid, free, confirmed ? 1 : 0, d_r);
      if (tick.valid && tick.n > 0) {
        out.valid = 1;
        out.n_points = std::min<std::uint8_t>(tick.n, 32);
        for (std::uint8_t i = 0; i < out.n_points; ++i) {
          out.x_m[i] = tick.x[i];
          out.y_m[i] = tick.y[i];
          out.yaw_rad[i] = tick.yaw[i];
        }
      }
    }
    (void)traj.Send(out);
  }
  waitset.MarkForDestruction();
  return 0;
}
