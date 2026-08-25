// vehicle_can_gateway — façade: VehicleState → EgoMotion + Perception_In;
// SIL egress: Trajectory → GfChannel vehicle_cmd (not locked to CAN).

#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_ara/runtime/process_bringup.hpp"
#include "gf_gen/proxy/trajectory_proxy.hpp"
#include "gf_gen/skeleton/ego_motion_skeleton.hpp"
#include "gf_gen/skeleton/perception__in__st_skeleton.hpp"

#if __has_include("gf_gen/frame_ingest_config.hpp")
#include "gf_gen/frame_ingest_config.hpp"
#define GF_GW_HAS_FRAME_INGEST 1
#endif

#include "gf_channel/gf_channel.h"
#include "gf_channel/boundary_pods.h"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <chrono>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

namespace {

constexpr const char* kProcess = "adapter.vehicle_can_gateway";

constexpr const char* kSlotVehicleState = "gf.channel.vehicle_state";
constexpr const char* kSlotVehicleCmd = "gf.channel.vehicle_cmd";

struct VehicleState {
  std::uint64_t timestamp_ns{0};
  float speed_mps{0.0f};
  float yaw_rate_degps{0.0f};
  float steer_angle_deg{0.0f};
  std::uint8_t gear{4};
  bool valid{false};
};

struct CtrlSnapshot {
  float throttle{0.0f};
  float brake{0.0f};
  float steer{0.0f};
  float target_speed_mps{0.0f};
  std::uint8_t ctrl_mode{0};
  bool has{false};
};

std::uint64_t now_ns() {
  return static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(
          std::chrono::steady_clock::now().time_since_epoch())
          .count());
}

const char* EgoSource() {
  const char* v = std::getenv("GF_EGO_SOURCE");
#if defined(GF_GW_HAS_FRAME_INGEST)
  if (!v || !v[0]) {
    v = gf_gen::frame_ingest::kEgoSource;
  }
#endif
  // "carla" means vehicle_state GfChannel from local bridge (not json).
  return (v && v[0]) ? v : "gateway";
}

const char* CtrlModeName(std::uint8_t mode) {
  switch (mode) {
    case 1:
      return "acc";
    case 2:
      return "aeb";
    case 3:
      return "pullaway";
    default:
      return "cruise";
  }
}

std::uint8_t LaneCode(const char* lane) {
  if (!lane) {
    return 0;
  }
  if (std::strcmp(lane, "left") == 0) {
    return 1;
  }
  if (std::strcmp(lane, "right") == 0) {
    return 2;
  }
  return 0;
}

const char* LaneFromYEnd(float y_end) {
  if (y_end > 0.4f) {
    return "left";
  }
  if (y_end < -0.4f) {
    return "right";
  }
  return "none";
}

void ProjectEgo(const VehicleState& st, gf_gen::EgoMotion* ego) {
  ego->timestamp_ns = st.timestamp_ns ? st.timestamp_ns : now_ns();
  ego->speed_mps = st.speed_mps;
  ego->yaw_rate_degps = st.yaw_rate_degps;
  ego->steer_angle_deg = st.steer_angle_deg;
  ego->gear = st.gear;
}

void ProjectPercIn(const VehicleState& st, std::uint32_t frame,
                   gf_gen::Perception_In_St* pin) {
  pin->timestamp_ns = st.timestamp_ns ? st.timestamp_ns : now_ns();
  pin->ipc_frame_counter = frame;
  pin->gear = st.gear;
  pin->vehicle_speed = st.speed_mps;
  pin->yaw_rate = st.yaw_rate_degps;
  pin->_vendor_payload_opaque[0] = 0;
}

bool IngestFromChannel(GfChannel* ch, std::uint64_t* last_seq, VehicleState* st) {
  if (!ch) {
    return false;
  }
  GfVehicleStatePod pod{};
  std::uint32_t got = 0;
  std::uint64_t ts = 0;
  std::uint32_t w = 0;
  std::uint32_t h = 0;
  std::uint16_t fmt = 0;
  const int r = gf_channel_latest(ch, &pod, sizeof(pod), &got, last_seq, &ts, &w, &h, &fmt);
  if (r != 1 || got < sizeof(GfVehicleStatePod)) {
    return false;
  }
  if (pod.magic != GF_CH_VEHICLE_STATE_MAGIC || pod.version != GF_CH_POD_VERSION) {
    return false;
  }
  st->timestamp_ns = pod.timestamp_ns ? pod.timestamp_ns : ts;
  st->speed_mps = pod.speed_mps;
  st->yaw_rate_degps = pod.yaw_rate_degps;
  st->steer_angle_deg = pod.steer_angle_deg;
  st->gear = pod.gear ? pod.gear : 4;
  st->valid = true;
  return true;
}

void StubTick(std::uint64_t frame, VehicleState* st) {
  st->timestamp_ns = now_ns();
  st->speed_mps = 5.0f + static_cast<float>(frame % 10) * 0.1f;
  st->yaw_rate_degps = 0.1f;
  st->steer_angle_deg = 2.0f;
  st->gear = 4;
  st->valid = true;
}

void PublishCmd(GfChannel* ch, const char* lane, const VehicleState& st,
                const CtrlSnapshot& ctrl, std::uint64_t seq) {
  // Caller gates on ctrl.has — never invent thr/steer before first Trajectory.
  if (!ch || !ctrl.has) {
    return;
  }
  GfVehicleCmdPod pod{};
  pod.magic = GF_CH_VEHICLE_CMD_MAGIC;
  pod.version = GF_CH_POD_VERSION;
  pod.timestamp_ns = now_ns();
  pod.seq = seq;
  pod.throttle = ctrl.throttle;
  pod.brake = ctrl.brake;
  pod.steer = ctrl.steer;
  pod.target_speed_mps = ctrl.target_speed_mps;
  pod.speed_mps = st.speed_mps;
  pod.ctrl_mode = ctrl.ctrl_mode;
  pod.lane_code = LaneCode(lane);
  (void)gf_channel_publish(ch, &pod, sizeof(pod), pod.timestamp_ns, seq);
}

}  // namespace

int main(int argc, char** argv) {
  int max_traj = 0;
  if (argc > 1) {
    max_traj = std::atoi(argv[1]);
  }

  gf_ara::com::binding::iceoryx::InitRuntime("gf-vehicle-can-gateway");

  gf_ara::runtime::ProcessSupervisor supervisor;
  if (!supervisor.Start(kProcess)) {
    std::cerr << "[ERROR] vehicle_can_gateway: ProcessSupervisor.Start failed\n";
    return EXIT_FAILURE;
  }

  const std::string ego_src = EgoSource();
  // inject / carla / gateway all keep this process; inject feeds vehicle_state slot
  // (or stub). Gateway always Provides Ego + Perception_In (unique provider).

  gf_gen::EgoMotionSkeleton ego_pub{};
  gf_gen::Perception_In_StSkeleton perc_in_pub{};
  gf_gen::TrajectoryProxy traj_sub{};

  GfChannel* state_ch = nullptr;
  GfChannel* cmd_ch = nullptr;
  const bool want_channel = (ego_src == "carla" || ego_src == "inject" ||
                             ego_src == "vehicle_bus" || ego_src == "channel");
  if (want_channel) {
    // Reader opens after writer create; retry in loop if needed.
    state_ch = gf_channel_open(kSlotVehicleState);
  }
  // SIL egress channel: gateway Creates so bridge can Open.
  cmd_ch = gf_channel_create_blob(kSlotVehicleCmd, sizeof(GfVehicleCmdPod), 2);
  if (!cmd_ch) {
    std::cerr << "[WARN] vehicle_can_gateway: vehicle_cmd create failed errno=" << errno
              << " (SIL egress disabled)\n";
  }

  std::uint64_t frame = 0;
  int got_traj = 0;
  std::uint64_t cmd_seq = 0;
  std::string last_lane = "none";
  VehicleState state{};
  CtrlSnapshot last_ctrl{};
  std::uint64_t state_seq = 0;

  std::cout << "gf-vehicle-can-gateway: start ego_source=" << ego_src
            << " (VehicleState→Ego+In; cmd via GfChannel)\n";

  while (!iox::posix::hasTerminationRequested()) {
    supervisor.Tick();
    if (supervisor.ExitForEmRestart()) {
      return gf_ara::exec::kEmRestartExitCode;
    }

    if (want_channel && !state_ch) {
      state_ch = gf_channel_open(kSlotVehicleState);
    }

    bool updated = false;
    if (state_ch) {
      updated = IngestFromChannel(state_ch, &state_seq, &state);
    }
    if (!state.valid) {
      if (ego_src == "gateway" || ego_src == "stub") {
        StubTick(frame, &state);
        updated = true;
      } else {
        // Wait for first vehicle_state from local bridge / inject feeder.
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
        ++frame;
        continue;
      }
    } else if (!updated && (ego_src == "gateway" || ego_src == "stub")) {
      StubTick(frame, &state);
    }

    gf_gen::EgoMotion ego{};
    ProjectEgo(state, &ego);
    (void)ego_pub.Send(ego);

    gf_gen::Perception_In_St pin{};
    ProjectPercIn(state, static_cast<std::uint32_t>(frame), &pin);
    (void)perc_in_pub.Send(pin);

    const char* lane = last_lane.c_str();
    float y_end = 0.0f;
    auto taken = traj_sub.Take();
    if (taken && taken.Value().has_value()) {
      const auto& t = *taken.Value();
      ++got_traj;
      last_ctrl.throttle = t.throttle;
      last_ctrl.brake = t.brake;
      last_ctrl.steer = t.steer;
      last_ctrl.target_speed_mps = t.target_speed_mps;
      last_ctrl.ctrl_mode = t.ctrl_mode;
      last_ctrl.has = true;
      if (t.point_count > 0) {
        y_end = t.points_y_m[t.point_count - 1];
        lane = LaneFromYEnd(y_end);
        last_lane = lane;
      }
      std::cout << "gf-vehicle-can-gateway: Trajectory#" << got_traj
                << " points=" << static_cast<int>(t.point_count)
                << " y_end=" << y_end << " lane=" << lane
                << " thr=" << t.throttle << " brk=" << t.brake
                << " st=" << t.steer << " mode=" << CtrlModeName(t.ctrl_mode)
                << " ts_ns=" << t.timestamp_ns << std::endl;
      if (max_traj > 0 && got_traj >= max_traj) {
        std::cout << "gf-vehicle-can-gateway: received " << got_traj
                  << " Trajectory sample(s), exiting OK\n";
        if (cmd_ch) {
          gf_channel_close(cmd_ch);
        }
        if (state_ch) {
          gf_channel_close(state_ch);
        }
        return EXIT_SUCCESS;
      }
    }

    if (cmd_ch && last_ctrl.has) {
      ++cmd_seq;
      PublishCmd(cmd_ch, last_lane.c_str(), state, last_ctrl, cmd_seq);
    }

    ++frame;
    // SIL egress cadence ≈ CAN 10ms (gf-config publish_policy backlog may override later).
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }

  if (cmd_ch) {
    gf_channel_close(cmd_ch);
  }
  if (state_ch) {
    gf_channel_close(state_ch);
  }
  return EXIT_SUCCESS;
}
