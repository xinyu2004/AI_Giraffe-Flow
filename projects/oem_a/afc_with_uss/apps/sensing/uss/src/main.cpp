#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_demo/platform_sil.hpp"
#include "gf_gen/proxy/ego_motion_proxy.hpp"
#include "gf_gen/skeleton/uss_zones_skeleton.hpp"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <chrono>
#include <cstdlib>
#include <iostream>
#include <thread>

namespace {

constexpr const char* kProcess = "sensing.uss";

}  // namespace

int main() {
  gf_ara::com::binding::iceoryx::InitRuntime("gf-sensing-uss");

  gf::demo::platform_sil::ProcessSupervisor supervisor;
  if (!supervisor.Start(kProcess)) {
    return EXIT_FAILURE;
  }

  gf_gen::EgoMotionProxy ego_sub{};
  gf_gen::UssZonesSkeleton uss_pub{};

  std::uint64_t seq = 0;
  std::cout << "gf-sensing-uss: start\n";

  while (!iox::posix::hasTerminationRequested()) {
    supervisor.Tick();

    auto taken = ego_sub.Take();
    if (taken && taken.Value().has_value()) {
      const auto& ego = *taken.Value();
      gf_gen::UssZones z{};
      z.timestamp_ns = ego.timestamp_ns;
      z.sys_status = 1;
      z.nearest_cm = static_cast<std::uint8_t>(20 + (seq % 40));
      z.zone_mask = 0x3F;
      for (std::uint8_t i = 0; i < 6; ++i) {
        z.zones[i].zone_id = i;
        z.zones[i].status = 1;
        z.zones[i].distance_cm =
            static_cast<std::uint8_t>(z.nearest_cm + i);
      }
      if (static_cast<bool>(uss_pub.Send(z))) {
        std::cout << "gf-sensing-uss: UssZones#" << seq
                  << " nearest_cm=" << static_cast<int>(z.nearest_cm)
                  << " speed=" << ego.speed_mps << std::endl;
        ++seq;
      }
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
  }
  return EXIT_SUCCESS;
}
