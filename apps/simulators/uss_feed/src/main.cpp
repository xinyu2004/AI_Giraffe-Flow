#include "gf_ara/com/binding/iceoryx/runtime.hpp"

#if defined(GF_USE_GENERATED) && GF_USE_GENERATED
#include "gf_gen/skeleton/uss_zones_skeleton.hpp"
using Sample = gf_gen::UssZones;
using Publisher = gf_gen::UssZonesSkeleton;
#else
#include "gf_ara/com/binding/iceoryx/event.hpp"
#include "gf_ara/com/service_path.hpp"
#include "gf_demo/uss_zones_topic.hpp"
using Sample = gf::demo::uss_sensing::UssZones;
using Publisher = gf_ara::com::binding::iceoryx::EventPublisher<Sample>;
#endif

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <chrono>
#include <cstdint>
#include <iostream>
#include <thread>

int main() {
  gf_ara::com::binding::iceoryx::InitRuntime("gf-uss-feed");

#if defined(GF_USE_GENERATED) && GF_USE_GENERATED
  Publisher pub{};
#else
  Publisher pub{gf_ara::com::ServicePath{
      gf::demo::uss_sensing::kService,
      gf::demo::uss_sensing::kInstance,
      gf::demo::uss_sensing::kEvent,
  }};
#endif

  std::uint64_t seq = 0;
  while (!iox::posix::hasTerminationRequested()) {
    Sample sample{};
    sample.timestamp_ns = static_cast<std::uint64_t>(
        std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now().time_since_epoch())
            .count());
    sample.sys_status = 1;
    sample.nearest_cm = static_cast<std::uint8_t>(20 + (seq % 50));
    sample.zone_mask = 0x3F;
    for (std::uint8_t i = 0; i < 6; ++i) {
      sample.zones[i].zone_id = i;
      sample.zones[i].status = 1;
      sample.zones[i].distance_cm =
          static_cast<std::uint8_t>(sample.nearest_cm + i);
    }

#if defined(GF_USE_GENERATED) && GF_USE_GENERATED
    const bool ok = static_cast<bool>(pub.Send(sample));
#else
    const bool ok = static_cast<bool>(pub.Publish(sample));
#endif
    if (!ok) {
      std::cerr << "gf-uss-feed: publish failed\n";
    } else {
      std::cout << "gf-uss-feed: published seq=" << seq
                << " nearest_cm=" << static_cast<int>(sample.nearest_cm)
                << std::endl;
    }
    ++seq;
    std::this_thread::sleep_for(std::chrono::milliseconds(200));
  }
  return 0;
}
