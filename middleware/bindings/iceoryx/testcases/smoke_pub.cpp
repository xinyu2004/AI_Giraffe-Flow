#include "gf_ara/com/binding/iceoryx/event.hpp"
#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_ara/com/service_path.hpp"
#include "smoke_msg.hpp"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <chrono>
#include <cstdint>
#include <iostream>
#include <thread>

int main() {
  gf_ara::com::binding::iceoryx::InitRuntime("gf-iox-smoke-pub");
  gf_ara::com::binding::iceoryx::EventPublisher<IoxSmokeMsg> pub{
      gf_ara::com::ServicePath{kIoxSmokeService, kIoxSmokeInstance, kIoxSmokeEvent},
  };

  std::uint64_t seq = 0;
  while (!iox::posix::hasTerminationRequested()) {
    IoxSmokeMsg sample{};
    sample.seq = seq;
    sample.stamp_ns = static_cast<std::uint64_t>(
        std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now().time_since_epoch())
            .count());
    if (!pub.Publish(sample)) {
      std::cerr << "gf_iox_smoke_pub: publish failed seq=" << seq << '\n';
    } else {
      std::cout << "gf_iox_smoke_pub: seq=" << seq << '\n';
    }
    ++seq;
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
  }
  return 0;
}
