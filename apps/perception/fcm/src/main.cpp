#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_demo/platform_sil.hpp"
#include "gf_gen/proxy/perception__in__st_proxy.hpp"
#include "gf_gen/skeleton/perception_message__out__st_skeleton.hpp"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <chrono>
#include <cstdlib>
#include <iostream>
#include <thread>

namespace {

constexpr const char* kProcess = "perception.fcm";

}  // namespace

int main() {
  gf_ara::com::binding::iceoryx::InitRuntime("gf-perception-fcm");

  gf::demo::platform_sil::ProcessSupervisor supervisor;
  if (!supervisor.Start(kProcess)) {
    return EXIT_FAILURE;
  }

  gf_gen::Perception_In_StProxy in_sub{};
  gf_gen::Perception_MESSAGE_Out_StSkeleton out_pub{};

  std::uint64_t out_seq = 0;
  std::cout << "gf-perception-fcm: start\n";

  while (!iox::posix::hasTerminationRequested()) {
    supervisor.Tick();

    auto taken = in_sub.Take();
    if (taken && taken.Value().has_value()) {
      const auto& in = *taken.Value();
      gf_gen::Perception_MESSAGE_Out_St out{};
      out.timestamp_ns = in.timestamp_ns;
      out.dyn_obj_count = static_cast<std::uint8_t>(1 + (out_seq % 3));
      out.static_obj_count = 1;
      out._vendor_payload_opaque[0] = 0;
      if (static_cast<bool>(out_pub.Send(out))) {
        std::cout << "gf-perception-fcm: out#" << out_seq
                  << " dyn=" << static_cast<int>(out.dyn_obj_count)
                  << " frame=" << in.ipc_frame_counter << std::endl;
        ++out_seq;
      }
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
  }
  return EXIT_SUCCESS;
}
