#include "gf_ara/com/binding/iceoryx/event.hpp"
#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_ara/com/service_path.hpp"
#include "smoke_msg.hpp"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <chrono>
#include <cstdlib>
#include <iostream>
#include <thread>

int main(int argc, char** argv) {
  int max_recv = 5;
  if (argc > 1) {
    max_recv = std::atoi(argv[1]);
    if (max_recv <= 0) {
      max_recv = 5;
    }
  }

  gf_ara::com::binding::iceoryx::InitRuntime("gf-iox-smoke-sub");
  gf_ara::com::binding::iceoryx::EventSubscriber<IoxSmokeMsg> sub{
      gf_ara::com::ServicePath{kIoxSmokeService, kIoxSmokeInstance, kIoxSmokeEvent},
  };

  int got = 0;
  while (!iox::posix::hasTerminationRequested()) {
    auto taken = sub.Take();
    if (!taken) {
      std::cerr << "gf_iox_smoke_sub: Take error\n";
    } else if (taken.Value().has_value()) {
      const auto& s = *taken.Value();
      std::cout << "gf_iox_smoke_sub: seq=" << s.seq << '\n';
      ++got;
      if (got >= max_recv) {
        std::cout << "gf_iox_smoke_sub: received " << got << " sample(s)\n";
        return EXIT_SUCCESS;
      }
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
  }
  return EXIT_SUCCESS;
}
