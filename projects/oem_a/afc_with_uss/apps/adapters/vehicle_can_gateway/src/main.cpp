#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_demo/platform_sil.hpp"
#include "gf_gen/proxy/trajectory_proxy.hpp"
#include "gf_gen/skeleton/ego_motion_skeleton.hpp"
#include "gf_gen/skeleton/perception__in__st_skeleton.hpp"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <chrono>
#include <cstdlib>
#include <iostream>
#include <thread>

namespace {

constexpr const char* kProcess = "adapter.vehicle_can_gateway";

std::uint64_t now_ns() {
  return static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(
          std::chrono::steady_clock::now().time_since_epoch())
          .count());
}

}  // namespace

int main(int argc, char** argv) {
  int max_traj = 0;
  if (argc > 1) {
    max_traj = std::atoi(argv[1]);
  }

  gf_ara::com::binding::iceoryx::InitRuntime("gf-vehicle-can-gateway");

  gf::demo::platform_sil::ProcessSupervisor supervisor;
  if (!supervisor.Start(kProcess)) {
    return EXIT_FAILURE;
  }

  gf_gen::EgoMotionSkeleton ego_pub{};
  gf_gen::Perception_In_StSkeleton perc_in_pub{};
  gf_gen::TrajectoryProxy traj_sub{};

  std::uint64_t frame = 0;
  int got_traj = 0;

  std::cout << "gf-vehicle-can-gateway: start";
  if (max_traj > 0) {
    std::cout << " (exit after " << max_traj << " Trajectory)";
  }
  std::cout << std::endl;

  while (!iox::posix::hasTerminationRequested()) {
    supervisor.Tick();

    gf_gen::EgoMotion ego{};
    ego.timestamp_ns = now_ns();
    ego.speed_mps = 5.0f + static_cast<float>(frame % 10) * 0.1f;
    ego.yaw_rate_degps = 0.1f;
    ego.steer_angle_deg = 2.0f;
    ego.gear = 4;
    (void)ego_pub.Send(ego);

    gf_gen::Perception_In_St pin{};
    pin.timestamp_ns = ego.timestamp_ns;
    pin.ipc_frame_counter = static_cast<std::uint32_t>(frame);
    pin.gear = ego.gear;
    pin.vehicle_speed = ego.speed_mps;
    pin.yaw_rate = ego.yaw_rate_degps;
    pin._vendor_payload_opaque[0] = 0;
    (void)perc_in_pub.Send(pin);

    auto taken = traj_sub.Take();
    if (taken && taken.Value().has_value()) {
      const auto& t = *taken.Value();
      ++got_traj;
      std::cout << "gf-vehicle-can-gateway: Trajectory#" << got_traj
                << " points=" << static_cast<int>(t.point_count)
                << " ts_ns=" << t.timestamp_ns << std::endl;
      if (max_traj > 0 && got_traj >= max_traj) {
        std::cout << "gf-vehicle-can-gateway: received " << got_traj
                  << " Trajectory sample(s), exiting OK\n";
        return EXIT_SUCCESS;
      }
    }

    ++frame;
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
  }
  return EXIT_SUCCESS;
}
