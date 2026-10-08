#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_ara/com/binding/iceoryx/wait_set.hpp"
#include "gf_ara/runtime/process_bringup.hpp"
#include "gf_ara/sm/state_client.hpp"
#include "gf_gen/ego_motion.hpp"
#include "gf_gen/apa_status.hpp"
#include "gf_gen/vehicle_mode.hpp"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <cmath>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <string>

namespace {

constexpr const char* kProcess = "mode.drive_park";
constexpr uint8_t kDriving = 0;
constexpr uint8_t kSpotSearch = 1;
constexpr uint8_t kParking = 2;
constexpr float kSpotSearchMaxMps = 15.0f / 3.6f;
constexpr float kStopMps = 0.35f;
constexpr std::uint32_t kWaitSliceMs = 20;
constexpr std::uint64_t kIdEgo = 1;
constexpr std::uint64_t kIdApa = 2;

}  // namespace

int main() {
  gf_ara::com::binding::iceoryx::InitRuntime("gf-mode-drive-park");

  gf_ara::runtime::ProcessSupervisor supervisor;
  if (!supervisor.Start(kProcess)) {
    std::cerr << "[ERROR] mode.drive_park: ProcessSupervisor.Start failed\n";
    return EXIT_FAILURE;
  }

  using gf_ara::sm::StateClient;

  constexpr const char* kDriveParkFg = "DriveParkFG";
  constexpr const char* kDrivingActive = "DrivingActive";
  constexpr const char* kParkingActive = "ParkingActive";

  StateClient::EnsureGroupNamed(kDriveParkFg, kDrivingActive);
  (void)StateClient::RequestTransitionNamed(kDriveParkFg, kDrivingActive);

  gf_gen::EgoMotionProxy ego;
  gf_gen::ApaStatusProxy apa_st;
  gf_ara::com::binding::iceoryx::EventWaitSet<3> waitset;
  if (!waitset.AttachProxy(ego, kIdEgo) || !waitset.AttachProxy(apa_st, kIdApa)) {
    std::cerr << "[ERROR] mode.drive_park: EventWaitSet attach failed\n";
    return EXIT_FAILURE;
  }
  gf_gen::VehicleModeSkeleton mode_sk;

  uint8_t last_mode = 255;
  uint8_t last_sent_mode = 255;
  uint8_t last_sent_apa = 255;
  uint8_t last_sent_confirm = 255;
  float last_sent_v = -1.0f;
  uint8_t apa = 0;
  uint8_t confirm = 0;
  bool have_apa = false;
  std::string last_fg;
  std::cout << "mode.drive_park: EventWaitSet; VehicleMode=mode; FG from ApaStatus\n";

  while (!iox::posix::hasTerminationRequested()) {
    supervisor.Tick();
    if (supervisor.ExitForEmRestart()) {
      return gf_ara::exec::kEmRestartExitCode;
    }

    (void)waitset.TimedWaitMs(kWaitSliceMs);

    float v = 0.0f;
    std::uint64_t ego_ts = 0;
    bool have_ego = false;
    for (;;) {
      auto taken = ego.Take();
      if (!taken.HasValue() || !taken.Value().has_value()) {
        break;
      }
      v = taken.Value()->speed_mps;
      ego_ts = taken.Value()->timestamp_ns;
      have_ego = true;
    }

    bool apa_new = false;
    for (;;) {
      auto st = apa_st.Take();
      if (!st.HasValue() || !st.Value().has_value()) {
        break;
      }
      apa = st.Value()->uiAPAOnOff ? 1 : 0;
      confirm = st.Value()->uiAPAStatus ? 1 : 0;
      have_apa = true;
      apa_new = true;
    }

    if (!have_ego && !apa_new && last_sent_mode != 255) {
      continue;
    }

    uint8_t m = kDriving;
    if (confirm && v < kStopMps) {
      m = kParking;
    } else if (apa && v < kSpotSearchMaxMps) {
      m = kSpotSearch;
    }

    const char* fg_target = (m == kParking) ? kParkingActive : kDrivingActive;
    if (fg_target != last_fg) {
      if (StateClient::RequestTransitionNamed(kDriveParkFg, fg_target)) {
        std::cout << "mode.drive_park: SM SetState " << kDriveParkFg << "→" << fg_target
                  << " (VehicleMode=" << static_cast<int>(m) << " v=" << v << ")\n";
        last_fg = fg_target;
      }
    }

    const bool mode_changed =
        m != last_sent_mode || apa != last_sent_apa || confirm != last_sent_confirm ||
        apa_new || (last_sent_v < 0.0f) || (std::fabs(v - last_sent_v) > 0.05f);
    if (!mode_changed) {
      continue;
    }

    gf_gen::VehicleMode out{};
    out.timestamp_ns =
        ego_ts ? ego_ts
               : static_cast<uint64_t>(
                     std::chrono::duration_cast<std::chrono::nanoseconds>(
                         std::chrono::steady_clock::now().time_since_epoch())
                         .count());
    out.mode = m;
    out.speed_mps = v;
    out.apa_armed = apa;
    (void)mode_sk.Send(out);
    last_sent_mode = m;
    last_sent_apa = apa;
    last_sent_confirm = confirm;
    last_sent_v = v;
    if (m != last_mode) {
      std::cout << "mode.drive_park: VehicleMode=" << static_cast<int>(m) << " v=" << v
                << " apa=" << static_cast<int>(apa)
                << " confirm=" << static_cast<int>(confirm)
                << " have_apa=" << (have_apa ? 1 : 0) << '\n';
      last_mode = m;
    }
  }
  waitset.MarkForDestruction();
  return 0;
}
