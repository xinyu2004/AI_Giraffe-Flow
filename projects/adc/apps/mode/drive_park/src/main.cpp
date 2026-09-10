#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_ara/runtime/process_bringup.hpp"
#include "gf_ara/sm/state_client.hpp"
#include "gf_gen/proxy/ego_motion_proxy.hpp"
#include "gf_gen/skeleton/vehicle_mode_skeleton.hpp"
#include "gf_channel/gf_channel.h"
#include "gf_channel/boundary_pods.h"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <thread>

namespace {

constexpr const char* kProcess = "mode.drive_park";
constexpr uint8_t kDriving = 0;
constexpr uint8_t kSpotSearch = 1;
constexpr uint8_t kParking = 2;
constexpr float kSpotSearchMaxMps = 15.0f / 3.6f;
constexpr float kStopMps = 0.35f;

bool ReadModeHint(GfChannel* ch, std::uint64_t* last_seq, uint8_t* apa, uint8_t* confirm) {
  if (!ch || !last_seq || !apa || !confirm) {
    return false;
  }
  GfModeHintPod pod{};
  std::uint32_t got = 0;
  std::uint64_t ts = 0;
  std::uint32_t w = 0;
  std::uint32_t h = 0;
  std::uint16_t fmt = 0;
  const int n =
      gf_channel_latest(ch, &pod, sizeof(pod), &got, last_seq, &ts, &w, &h, &fmt);
  if (n <= 0 || got < sizeof(pod) || pod.magic != GF_CH_MODE_HINT_MAGIC ||
      pod.version != GF_CH_MODE_HINT_VERSION) {
    return false;
  }
  *apa = pod.apa_armed ? 1 : 0;
  *confirm = pod.slot_confirmed ? 1 : 0;
  return true;
}

}  // namespace

int main() {
  gf_ara::com::binding::iceoryx::InitRuntime("gf-mode-drive-park");

  gf_ara::runtime::ProcessSupervisor supervisor;
  if (!supervisor.Start(kProcess)) {
    std::cerr << "[ERROR] mode.drive_park: ProcessSupervisor.Start failed\n";
    return EXIT_FAILURE;
  }

  using gf_ara::sm::StateClient;

  // Product ModeDeclaration names — App-local, not middleware constants.
  constexpr const char* kDriveParkFg = "DriveParkFG";
  constexpr const char* kDrivingActive = "DrivingActive";
  constexpr const char* kParkingActive = "ParkingActive";

  StateClient::EnsureGroupNamed(kDriveParkFg, kDrivingActive);
  (void)StateClient::RequestTransitionNamed(kDriveParkFg, kDrivingActive);

  gf_gen::EgoMotionProxy ego;
  gf_gen::VehicleModeSkeleton mode_sk;

  const char* hint_slot = std::getenv("GF_MODE_HINT_SLOT");
  if (!hint_slot || !hint_slot[0]) {
    hint_slot = "gf.channel.mode_hint";
  }
  GfChannel* hint_ch = gf_channel_open(hint_slot);
  std::uint64_t hint_seq = 0;

  uint8_t last_mode = 255;
  std::string last_fg;
  while (!iox::posix::hasTerminationRequested()) {
    supervisor.Tick();
    if (supervisor.ExitForEmRestart()) {
      return gf_ara::exec::kEmRestartExitCode;
    }
    float v = 0.0f;
    if (auto taken = ego.Take(); taken.HasValue() && taken.Value().has_value()) {
      v = taken.Value()->speed_mps;
    }
    uint8_t apa = 0;
    uint8_t confirm = 0;
    if (const char* a = std::getenv("GF_APA_ARMED"); a && a[0] == '1') {
      apa = 1;
    }
    if (const char* c = std::getenv("GF_SLOT_CONFIRMED"); c && c[0] == '1') {
      confirm = 1;
    }
    if (!hint_ch) {
      hint_ch = gf_channel_open(hint_slot);
    }
    uint8_t apa_h = 0;
    uint8_t confirm_h = 0;
    if (ReadModeHint(hint_ch, &hint_seq, &apa_h, &confirm_h)) {
      apa = apa_h;
      confirm = confirm_h;
    }

    // VehicleMode (HUD / obs): SpotSearch is still DrivingActive for FG set-diff.
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

    gf_gen::VehicleMode out{};
    out.timestamp_ns = static_cast<uint64_t>(
        std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now().time_since_epoch())
            .count());
    out.mode = m;
    out.speed_mps = v;
    out.apa_armed = apa;
    out.slot_confirmed = confirm;
    (void)mode_sk.Send(out);
    if (m != last_mode) {
      std::cout << "mode.drive_park: VehicleMode=" << static_cast<int>(m)
                << " v=" << v << " apa=" << static_cast<int>(apa)
                << " confirm=" << static_cast<int>(confirm) << '\n';
      last_mode = m;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
  }
  if (hint_ch) {
    gf_channel_close(hint_ch);
  }
  return 0;
}
