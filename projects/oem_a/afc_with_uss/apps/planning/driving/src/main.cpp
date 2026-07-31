#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_demo/platform_sil.hpp"
#include "gf_gen/proxy/ego_motion_proxy.hpp"
#include "gf_gen/proxy/perception_message__out__st_proxy.hpp"
#include "gf_gen/proxy/uss_zones_proxy.hpp"
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
void FillCurvedTrajectory(const gf_gen::EgoMotion& ego,
                          const std::optional<gf_gen::UssZones>& uss,
                          gf_gen::Trajectory& traj) {
  const float speed = std::max(ego.speed_mps, 0.5f);
  const float yaw_rate_rad = ego.yaw_rate_degps * kDeg2Rad;
  const float steer_rad = ego.steer_angle_deg * kDeg2Rad;

  float kappa = 0.0f;
  if (std::fabs(yaw_rate_rad) > 1e-4f) {
    kappa = yaw_rate_rad / speed;
  } else {
    kappa = steer_rad / kWheelbaseM;
  }
  // Demo: make lane-change arcs readable in BEV (still ego-frame physics-ish)
  kappa *= 2.5f;
  constexpr float kMaxKappa = 0.15f;
  kappa = std::clamp(kappa, -kMaxKappa, kMaxKappa);

  float horizon_m = std::clamp(speed * 3.0f, 35.0f, 55.0f);
  // Only shorten when USS reports a very close obstacle (demo readability).
  if (uss && uss->nearest_cm > 0 && uss->nearest_cm < 80) {
    horizon_m = std::min(horizon_m, static_cast<float>(uss->nearest_cm) * 0.01f + 12.0f);
    horizon_m = std::max(horizon_m, 18.0f);
  }

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

  gf::demo::platform_sil::ProcessSupervisor supervisor;
  if (!supervisor.Start(kProcess)) {
    return EXIT_FAILURE;
  }

  gf_gen::Perception_MESSAGE_Out_StProxy perc_sub{};
  gf_gen::EgoMotionProxy ego_sub{};
  gf_gen::UssZonesProxy uss_sub{};
  gf_gen::TrajectorySkeleton traj_pub{};

  std::optional<gf_gen::Perception_MESSAGE_Out_St> last_perc;
  std::optional<gf_gen::EgoMotion> last_ego;
  std::optional<gf_gen::UssZones> last_uss;
  std::uint64_t seq = 0;

  std::cout << "gf-planning-driving: start (curved stub from steer/yaw)\n";

  while (!iox::posix::hasTerminationRequested()) {
    supervisor.Tick();

    if (auto t = perc_sub.Take(); t && t.Value().has_value()) {
      last_perc = *t.Value();
    }
    if (auto t = ego_sub.Take(); t && t.Value().has_value()) {
      last_ego = *t.Value();
    }
    if (auto t = uss_sub.Take(); t && t.Value().has_value()) {
      last_uss = *t.Value();
    }

    // Demo / inject: EgoMotion drives Trajectory. FCM optional.
    if (last_ego) {
      const auto& ego = *last_ego;
      const int dyn =
          last_perc ? static_cast<int>(last_perc->dyn_obj_count) : 0;
      const int nearest =
          last_uss ? static_cast<int>(last_uss->nearest_cm) : -1;

      gf_gen::Trajectory traj{};
      FillCurvedTrajectory(ego, last_uss, traj);
      if (static_cast<bool>(traj_pub.Send(traj))) {
        std::cout << "gf-planning-driving: Trajectory#" << seq
                  << " pts=" << static_cast<int>(traj.point_count)
                  << " y_end=" << traj.points_y_m[traj.point_count - 1]
                  << " dyn=" << dyn << " nearest_cm=" << nearest << std::endl;
        ++seq;
      }
      last_ego.reset();
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
  }
  return EXIT_SUCCESS;
}
