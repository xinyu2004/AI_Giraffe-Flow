#include "gf_ara/com/binding/iceoryx/runtime.hpp"

#if defined(GF_USE_GENERATED) && GF_USE_GENERATED
#include "gf_gen/proxy/uss_zones_proxy.hpp"
using Sample = gf_gen::UssZones;
using Subscriber = gf_gen::UssZonesProxy;
#else
#include "gf_ara/com/binding/iceoryx/event.hpp"
#include "gf_ara/com/service_path.hpp"
#include "gf_demo/uss_zones_topic.hpp"
using Sample = gf::demo::uss_sensing::UssZones;
using Subscriber = gf_ara::com::binding::iceoryx::EventSubscriber<Sample>;
#endif

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <chrono>
#include <cstdlib>
#include <iostream>
#include <thread>

int main(int argc, char** argv) {
  int max_recv = 0;
  if (argc > 1) {
    max_recv = std::atoi(argv[1]);
  }

  gf_ara::com::binding::iceoryx::InitRuntime("gf-demo-pipeline");

#if defined(GF_USE_GENERATED) && GF_USE_GENERATED
  Subscriber sub{};
#else
  Subscriber sub{gf_ara::com::ServicePath{
      gf::demo::uss_sensing::kService,
      gf::demo::uss_sensing::kInstance,
      gf::demo::uss_sensing::kEvent,
  }};
#endif

  int got = 0;
  while (!iox::posix::hasTerminationRequested()) {
    auto taken = sub.Take();
    if (!taken) {
      std::cerr << "gf-demo-pipeline: Take error\n";
    } else if (taken.Value().has_value()) {
      const auto& s = *taken.Value();
      std::cout << "gf-demo-pipeline: got nearest_cm="
                << static_cast<int>(s.nearest_cm)
                << " ts_ns=" << s.timestamp_ns << std::endl;
      ++got;
      if (max_recv > 0 && got >= max_recv) {
        std::cout << "gf-demo-pipeline: received " << got
                  << " sample(s), exiting\n";
        return EXIT_SUCCESS;
      }
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
  }
  return EXIT_SUCCESS;
}
