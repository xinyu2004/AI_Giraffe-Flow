#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_ara/runtime/process_bringup.hpp"
#include "gf_gen/proxy/ego_motion_proxy.hpp"
#include "gf_gen/proxy/perception__in__st_proxy.hpp"
#include "gf_gen/skeleton/perception_message__out__st_skeleton.hpp"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <chrono>
#include <cstdlib>
#include <iostream>
#include <optional>
#include <thread>

namespace {

constexpr const char* kProcess = "perception.fcm";

gf_gen::Perception_MESSAGE_Out_St MakeStubOut(std::uint64_t timestamp_ns,
                                              std::uint64_t seq) {
  gf_gen::Perception_MESSAGE_Out_St out{};
  out.timestamp_ns = timestamp_ns;
  out.dyn_obj_count = static_cast<std::uint8_t>(1 + (seq % 3));
  out.static_obj_count = 1;
  out._vendor_payload_opaque[0] = 0;
  return out;
}

}  // namespace

int main() {
  gf_ara::com::binding::iceoryx::InitRuntime("gf-perception-fcm");

  gf_ara::runtime::ProcessSupervisor supervisor;
  if (!supervisor.Start(kProcess)) {
    return EXIT_FAILURE;
  }

  gf_gen::Perception_In_StProxy in_sub{};
  gf_gen::EgoMotionProxy ego_sub{};
  gf_gen::Perception_MESSAGE_Out_StSkeleton out_pub{};

  std::uint64_t out_seq = 0;
  std::cout << "gf-perception-fcm: start\n";

  while (!iox::posix::hasTerminationRequested()) {
    supervisor.Tick();
    if (supervisor.ExitForEmRestart()) {
      return gf_ara::exec::kEmRestartExitCode;
    }

    bool sent = false;
    auto taken = in_sub.Take();
    if (taken && taken.Value().has_value()) {
      const auto& in = *taken.Value();
      auto out = MakeStubOut(in.timestamp_ns, out_seq);
      if (static_cast<bool>(out_pub.Send(out))) {
        std::cout << "gf-perception-fcm: out#" << out_seq
                  << " dyn=" << static_cast<int>(out.dyn_obj_count)
                  << " frame=" << in.ipc_frame_counter << std::endl;
        ++out_seq;
        sent = true;
      }
    }

    // Inject path: gateway (Perception_In) is off — drive stub from EgoMotion.
    if (!sent) {
      auto ego_taken = ego_sub.Take();
      if (ego_taken && ego_taken.Value().has_value()) {
        const auto& ego = *ego_taken.Value();
        auto out = MakeStubOut(ego.timestamp_ns, out_seq);
        if (static_cast<bool>(out_pub.Send(out))) {
          std::cout << "gf-perception-fcm: out#" << out_seq
                    << " dyn=" << static_cast<int>(out.dyn_obj_count)
                    << " from=EgoMotion" << std::endl;
          ++out_seq;
        }
      }
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
  }
  return EXIT_SUCCESS;
}
