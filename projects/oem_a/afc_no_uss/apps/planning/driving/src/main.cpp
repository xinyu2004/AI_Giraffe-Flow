#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_ara/runtime/process_bringup.hpp"
#include "gf_gen/proxy/ego_motion_proxy.hpp"
#include "gf_gen/proxy/perception_message__out__st_proxy.hpp"
#include "gf_gen/skeleton/trajectory_skeleton.hpp"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <optional>
#include <thread>

namespace {

constexpr const char* kProcess = "planning.driving";
constexpr int kTrajPoints = 16;
constexpr float kWheelbaseM = 2.8f;
constexpr float kDeg2Rad = 0.017453292519943295f;

// Ego-frame path: +x forward, +y left. Curvature from yaw_rate (prefer) or steer.
void FillCurvedTrajectory(const gf_gen::EgoMotion& ego, gf_gen::Trajectory& traj) {
  const float speed = std::max(ego.speed_mps, 0.5f);
  const float yaw_rate_rad = ego.yaw_rate_degps * kDeg2Rad;
  const float steer_rad = ego.steer_angle_deg * kDeg2Rad;

  float kappa = 0.0f;
  if (std::fabs(yaw_rate_rad) > 1e-4f) {
    kappa = yaw_rate_rad / speed;
  } else {
    kappa = steer_rad / kWheelbaseM;
  }
  // Demo: make lane-change arcs readable in BEV
  kappa *= 2.5f;
  constexpr float kMaxKappa = 0.15f;
  kappa = std::clamp(kappa, -kMaxKappa, kMaxKappa);

  const float horizon_m = std::clamp(speed * 3.0f, 35.0f, 55.0f);
  const float ds = horizon_m / static_cast<float>(kTrajPoints - 1);
  float x = 0.0f;
  float y = 0.0f;
  float psi = 0.0f;

  traj.timestamp_ns = ego.timestamp_ns;
  traj.point_count = static_cast<std::uint8_t>(kTrajPoints);
  traj.gear_shift_first = ego.gear;
  traj.gear_shift_second = 0;

  for (int i = 0; i < kTrajPoints; ++i) {
    traj.points_x_m[i] = x;
    traj.points_y_m[i] = y;
    psi += kappa * ds;
    x += ds * std::cos(psi);
    y += ds * std::sin(psi);
  }
}

}  // namespace

int main() {
  gf_ara::com::binding::iceoryx::InitRuntime("gf-planning-driving");

  gf_ara::runtime::ProcessSupervisor supervisor;
  if (!supervisor.Start(kProcess)) {
    return EXIT_FAILURE;
  }

  gf_gen::Perception_MESSAGE_Out_StProxy perc_sub{};
  gf_gen::EgoMotionProxy ego_sub{};
  gf_gen::TrajectorySkeleton traj_pub{};

  std::optional<gf_gen::Perception_MESSAGE_Out_St> last_perc;
  std::optional<gf_gen::EgoMotion> last_ego;
  std::uint64_t seq = 0;

  std::cout << "gf-planning-driving: start (afc_no_uss; no USS)\n";

  while (!iox::posix::hasTerminationRequested()) {
    supervisor.Tick();
    if (supervisor.ExitForEmRestart()) {
      return gf_ara::exec::kEmRestartExitCode;
    }

    if (auto t = perc_sub.Take(); t && t.Value().has_value()) {
      last_perc = *t.Value();
    }
    if (auto t = ego_sub.Take(); t && t.Value().has_value()) {
      last_ego = *t.Value();
    }

    // EgoMotion drives Trajectory; FCM optional (dyn count logged only).
    if (last_ego) {
      const auto& ego = *last_ego;
      const int dyn =
          last_perc ? static_cast<int>(last_perc->dyn_obj_count) : 0;

      gf_gen::Trajectory traj{};
      FillCurvedTrajectory(ego, traj);
      if (static_cast<bool>(traj_pub.Send(traj))) {
        std::cout << "gf-planning-driving: Trajectory#" << seq
                  << " pts=" << static_cast<int>(traj.point_count)
                  << " y_end=" << traj.points_y_m[traj.point_count - 1]
                  << " dyn=" << dyn << std::endl;
        ++seq;
      }
      last_ego.reset();
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
  }
  return EXIT_SUCCESS;
}
