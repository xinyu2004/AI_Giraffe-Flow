#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_demo/platform_sil.hpp"
#include "gf_gen/proxy/ego_motion_proxy.hpp"
#include "gf_gen/proxy/perception_message__out__st_proxy.hpp"
#include "gf_gen/proxy/uss_zones_proxy.hpp"
#include "gf_gen/skeleton/trajectory_skeleton.hpp"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <chrono>
#include <cstdlib>
#include <iostream>
#include <optional>
#include <thread>

namespace {

constexpr const char* kProcess = "planning.driving";

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

  std::cout << "gf-planning-driving: start\n";

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

    if (last_perc && last_ego && last_uss) {
      gf_gen::Trajectory traj{};
      traj.timestamp_ns = last_ego->timestamp_ns;
      traj.point_count = 3;
      traj.points_x_m[0] = 0.0f;
      traj.points_y_m[0] = 0.0f;
      traj.points_x_m[1] = last_ego->speed_mps;
      traj.points_y_m[1] = 0.5f;
      traj.points_x_m[2] = last_ego->speed_mps * 2.0f;
      traj.points_y_m[2] = 1.0f;
      traj.gear_shift_first = last_ego->gear;
      traj.gear_shift_second = 0;
      if (static_cast<bool>(traj_pub.Send(traj))) {
        std::cout << "gf-planning-driving: Trajectory#" << seq
                  << " dyn=" << static_cast<int>(last_perc->dyn_obj_count)
                  << " nearest_cm=" << static_cast<int>(last_uss->nearest_cm)
                  << std::endl;
        ++seq;
      }
      last_perc.reset();
      last_ego.reset();
      last_uss.reset();
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
  }
  return EXIT_SUCCESS;
}
