// vehicle_can_gateway — façade: VehicleState → EgoMotion + Perception_In;
// SIL egress: forward live Trajectory / ParkingTrajectory → vehicle_cmd
// (DriveParkFG set-diff: only one planner process is alive).

#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_ara/com/binding/iceoryx/wait_set.hpp"
#include "gf_ara/com/binding/iceoryx/period_timer.hpp"
#include "gf_ara/runtime/process_bringup.hpp"
#include "gf_gen/parking_trajectory.hpp"
#include "gf_gen/driving_trajectory.hpp"
#include "gf_gen/ego_motion.hpp"
#include "gf_gen/perception__in__st.hpp"
#include "gf_gen/parking_slot.hpp"
#include "gf_gen/apa_status.hpp"
#include "gf_gen/frame_ingest_config.hpp"
#include "gf_gen/publish_policy.hpp"

#include "gf_ara/log/logger.hpp"
#include "gf_channel/gf_channel.h"
#include "gf_channel/boundary_pods.h"
#include "gf_app/frame_watch.hpp"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <chrono>
#include <cmath>
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
  if (!v || !v[0]) {
    v = gf_gen::frame_ingest::kEgoSource;
  }
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

void ProjectEgo(const VehicleState& st, std::uint64_t pub_ts, gf_gen::EgoMotion* ego) {
  ego->timestamp_ns = pub_ts;
  ego->speed_mps = st.speed_mps;
  ego->yaw_rate_degps = st.yaw_rate_degps;
  ego->steer_angle_deg = st.steer_angle_deg;
  ego->gear = st.gear;
}

void ProjectPercIn(const VehicleState& st, std::uint32_t in_seq, std::uint64_t pub_ts,
                   gf_gen::Perception_In_St* pin) {
  pin->timestamp_ns = pub_ts;
  pin->ipc_frame_counter = in_seq;
  pin->gear = st.gear;
  pin->vehicle_speed = st.speed_mps;
  pin->yaw_rate = st.yaw_rate_degps;
  pin->_vendor_payload_opaque[0] = 0;
}

std::uint32_t ServicePeriodMs(const char* id) {
  const auto* p = gf_gen::publish_policy::FindService(id);
  if (p && p->period_ms > 0) {
    return p->period_ms;
  }
  return 0;
}

std::uint32_t ChannelPeriodMs(const char* id) {
  const auto* p = gf_gen::publish_policy::FindChannel(id);
  if (p && p->period_ms > 0) {
    return p->period_ms;
  }
  return 0;
}

bool PeriodDue(std::uint64_t last_pub_ns, std::uint32_t period_ms, std::uint64_t now) {
  if (period_ms == 0) {
    return false;
  }
  if (last_pub_ns == 0) {
    return true;
  }
  return now - last_pub_ns >= static_cast<std::uint64_t>(period_ms) * 1000000ULL;
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

void StubTick(std::uint64_t in_seq, VehicleState* st) {
  st->timestamp_ns = now_ns();
  st->speed_mps = 5.0f + static_cast<float>(in_seq % 10) * 0.1f;
  st->yaw_rate_degps = 0.1f;
  st->steer_angle_deg = 2.0f;
  st->gear = 4;
  st->valid = true;
}

bool IngestModeHint(GfChannel* ch, std::uint64_t* last_seq, uint8_t* apa, uint8_t* confirm,
                    float p[6]) {
  if (!ch || !last_seq || !apa || !confirm || !p) {
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
  if (n <= 0 || got < 24 || pod.magic != GF_CH_MODE_HINT_MAGIC || pod.version < 1) {
    return false;
  }
  *apa = pod.apa_armed ? 1 : 0;
  *confirm = pod.slot_confirmed ? 1 : 0;
  if (pod.version >= 2 && got >= sizeof(pod)) {
    p[0] = pod.fParkingSlot_P0X;
    p[1] = pod.fParkingSlot_P0Y;
    p[2] = pod.fParkingSlot_P1X;
    p[3] = pod.fParkingSlot_P1Y;
    p[4] = pod.fParkingSlot_P2X;
    p[5] = pod.fParkingSlot_P2Y;
  }
  return true;
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
  gf_gen::ParkingSlotSkeleton slot_pub{};
  gf_gen::ApaStatusSkeleton apa_pub{};
  gf_gen::DrivingTrajectoryProxy traj_sub{};
  gf_gen::ParkingTrajectoryProxy park_traj_sub{};
  // VehicleMode is observational only; DriveParkFG set-diff selects the live planner.
  // HMI P* + confirmed land on ParkingSlot (gold fields), not VehicleMode / IPC_CanInfo.

  GfChannel* state_ch = nullptr;
  GfChannel* cmd_ch = nullptr;
  const char* hint_slot = std::getenv("GF_MODE_HINT_SLOT");
  if (!hint_slot || !hint_slot[0]) {
    hint_slot = "gf.channel.mode_hint";
  }
  GfChannel* hint_ch = gf_channel_open(hint_slot);
  std::uint64_t hint_seq = 0;
  uint8_t hint_apa = 0;
  uint8_t hint_confirm = 0;
  float hint_p[6] = {};
  if (const char* a = std::getenv("GF_APA_ARMED"); a && a[0] == '1') {
    hint_apa = 1;
  }
  if (const char* c = std::getenv("GF_SLOT_CONFIRMED"); c && c[0] == '1') {
    hint_confirm = 1;
  }
  uint8_t last_slot_apa = 255;
  uint8_t last_slot_confirm = 255;
  float last_slot_p[6] = {};
  uint8_t last_apa_on = 255;
  uint8_t last_apa_st = 255;
  bool have_slot_src = (hint_apa != 0 || hint_confirm != 0);
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

  std::uint64_t ego_seq = 0;
  std::uint64_t pin_seq = 0;
  int got_traj = 0;
  std::uint64_t cmd_seq = 0;
  std::string last_lane = "none";
  VehicleState state{};
  CtrlSnapshot last_ctrl{};
  std::uint64_t state_seq = 0;

  std::uint64_t last_stub_ns = 0;
  std::uint64_t last_ego_pub_ns = 0;
  std::uint64_t last_in_pub_ns = 0;
  std::uint64_t last_cmd_pub_ns = 0;
  std::uint64_t last_ingest_wall = 0;
  bool ingest_stale = false;
  const std::uint32_t ego_period_ms = ServicePeriodMs("EgoMotion");
  const std::uint32_t in_period_ms = ServicePeriodMs("Perception_In_St");
  const std::uint32_t cmd_period_ms = ChannelPeriodMs("vehicle_cmd");
  const std::uint32_t ingest_timeout_ms = [&]() {
    const std::uint32_t p = ego_period_ms ? ego_period_ms : in_period_ms;
    if (p == 0) {
      return 0u;
    }
    const std::uint32_t t = p * 10u;
    return t < 100u ? 100u : t;
  }();
  gf_app::EnsureDiagLogSinks();
  gf_app::FrameWatch rx_state;
  gf_app::FrameWatch rx_traj;
  gf_app::FrameWatch tx_cmd;
  gf_app::FrameWatch tx_ego;
  gf_app::FrameWatch tx_in;
  rx_state.Init("gw", "rx.vehicle_state");
  rx_state.BindChannel("vehicle_state");
  rx_traj.Init("gw", "rx.traj");
  rx_traj.BindService("DrivingTrajectory");
  tx_cmd.Init("gw", "tx.cmd");
  tx_cmd.BindChannel("vehicle_cmd");
  tx_cmd.EnablePeriodSilence();
  tx_ego.Init("gw", "tx.ego");
  tx_ego.BindService("EgoMotion");
  tx_ego.EnablePeriodSilence();
  tx_in.Init("gw", "tx.perc_in");
  tx_in.BindService("Perception_In_St");
  tx_in.EnablePeriodSilence();

  std::cout << "gf-vehicle-can-gateway: start ego_source=" << ego_src
            << " Ego/In period_ms=" << ego_period_ms << "/" << in_period_ms
            << " hold-last (seq/ts advance; speed=0 is not stale)"
            << " ingest_timeout_ms=" << ingest_timeout_ms
            << " cmd period_ms=" << cmd_period_ms
            << " ParkingSlot/ApaStatus on_change"
            << " traj forward=DriveParkFG set-diff (no VehicleMode mux)"
            << "; EventWaitSet+PeriodTimer (no private 1ms sleep)"
            << "; frame_watch=identity+budget ego[" << tx_ego.PolicyHint()
            << "] cmd[" << tx_cmd.PolicyHint() << "])\n";

  constexpr std::uint64_t kIdTraj = 1;
  constexpr std::uint64_t kIdPark = 2;
  constexpr std::uint64_t kIdPeriod = 3;
  gf_ara::com::binding::iceoryx::EventWaitSet<8> waitset;
  if (!waitset.AttachProxy(traj_sub, kIdTraj) || !waitset.AttachProxy(park_traj_sub, kIdPark)) {
    std::cerr << "[ERROR] vehicle_can_gateway: EventWaitSet attach failed\n";
    return EXIT_FAILURE;
  }
  std::uint32_t period_tick_ms = ego_period_ms ? ego_period_ms : 10u;
  if (in_period_ms && in_period_ms < period_tick_ms) {
    period_tick_ms = in_period_ms;
  }
  if (cmd_period_ms && cmd_period_ms < period_tick_ms) {
    period_tick_ms = cmd_period_ms;
  }
  gf_ara::com::binding::iceoryx::PeriodTimer period_timer;
  if (!period_timer.Start(waitset, kIdPeriod, period_tick_ms)) {
    std::cerr << "[ERROR] vehicle_can_gateway: PeriodTimer start failed\n";
    return EXIT_FAILURE;
  }

  auto publish_ego = [&](std::uint64_t now) {
    gf_gen::EgoMotion ego{};
    ProjectEgo(state, now, &ego);
    if (static_cast<bool>(ego_pub.Send(ego))) {
      ++ego_seq;
      tx_ego.Observe(ego_seq, ego.timestamp_ns);
      last_ego_pub_ns = now;
    }
  };

  auto publish_in = [&](std::uint64_t now) {
    const auto next = static_cast<std::uint32_t>(pin_seq + 1);
    gf_gen::Perception_In_St pin{};
    ProjectPercIn(state, next, now, &pin);
    if (static_cast<bool>(perc_in_pub.Send(pin))) {
      pin_seq = next;
      tx_in.Observe(pin_seq, pin.timestamp_ns);
      last_in_pub_ns = now;
    }
  };

  auto publish_slot = [&](std::uint64_t now) {
    gf_gen::ParkingSlot out{};
    out.timestamp_ns = now;
    out.fParkingSlot_P0X = hint_p[0];
    out.fParkingSlot_P0Y = hint_p[1];
    out.fParkingSlot_P1X = hint_p[2];
    out.fParkingSlot_P1Y = hint_p[3];
    out.fParkingSlot_P2X = hint_p[4];
    out.fParkingSlot_P2Y = hint_p[5];
    out.uiAPAOnOff = hint_apa;
    out.uiAPAStatus = hint_confirm;
    if (static_cast<bool>(slot_pub.Send(out))) {
      last_slot_apa = hint_apa;
      last_slot_confirm = hint_confirm;
      for (int i = 0; i < 6; ++i) {
        last_slot_p[i] = hint_p[i];
      }
    }
  };

  auto publish_apa = [&](std::uint64_t now) {
    gf_gen::ApaStatus out{};
    out.timestamp_ns = now;
    out.uiAPAOnOff = hint_apa;
    out.uiAPAStatus = hint_confirm;
    if (static_cast<bool>(apa_pub.Send(out))) {
      last_apa_on = hint_apa;
      last_apa_st = hint_confirm;
    }
  };

  auto publish_cmd = [&]() {
    // period hold-last; caller also invokes on new Traj (AEB edge). Not freeze.
    if (!cmd_ch || !last_ctrl.has) {
      return;
    }
    ++cmd_seq;
    PublishCmd(cmd_ch, last_lane.c_str(), state, last_ctrl, cmd_seq);
    tx_cmd.Observe(cmd_seq, now_ns());
    last_cmd_pub_ns = now_ns();
  };

  while (!iox::posix::hasTerminationRequested()) {
    supervisor.Tick();
    if (supervisor.ExitForEmRestart()) {
      period_timer.Stop();
      waitset.MarkForDestruction();
      return gf_ara::exec::kEmRestartExitCode;
    }

    (void)waitset.TimedWaitMs(period_tick_ms);

    if (want_channel && !state_ch) {
      state_ch = gf_channel_open(kSlotVehicleState);
    }
    if (!hint_ch) {
      hint_ch = gf_channel_open(hint_slot);
    }

    const std::uint64_t now = now_ns();
    uint8_t apa_h = hint_apa;
    uint8_t confirm_h = hint_confirm;
    float p_h[6] = {};
    for (int i = 0; i < 6; ++i) {
      p_h[i] = hint_p[i];
    }
    if (IngestModeHint(hint_ch, &hint_seq, &apa_h, &confirm_h, p_h)) {
      hint_apa = apa_h;
      hint_confirm = confirm_h;
      for (int i = 0; i < 6; ++i) {
        hint_p[i] = p_h[i];
      }
      have_slot_src = true;
    }
    bool slot_changed = have_slot_src && (last_slot_apa == 255 || hint_apa != last_slot_apa ||
                                          hint_confirm != last_slot_confirm);
    if (!slot_changed && have_slot_src) {
      for (int i = 0; i < 6; ++i) {
        if (std::fabs(hint_p[i] - last_slot_p[i]) > 0.01f) {
          slot_changed = true;
          break;
        }
      }
    }
    if (slot_changed) {
      publish_slot(now);
    }
    const bool apa_changed =
        have_slot_src && (last_apa_on == 255 || hint_apa != last_apa_on ||
                          hint_confirm != last_apa_st);
    if (apa_changed) {
      publish_apa(now);
    }
    bool state_fresh = false;
    if (state_ch) {
      state_fresh = IngestFromChannel(state_ch, &state_seq, &state);
      if (state_fresh) {
        last_ingest_wall = now;
        rx_state.Observe(0, state.timestamp_ns, false, true);
      }
    } else if (ego_src == "stub") {
      // Explicit stub only — never invent Ego under ego_source=gateway.
      const std::uint32_t stub_ms = ego_period_ms ? ego_period_ms : in_period_ms;
      if (stub_ms != 0 &&
          (last_stub_ns == 0 || now - last_stub_ns >=
                                    static_cast<std::uint64_t>(stub_ms) * 1000000ULL)) {
        StubTick(ego_seq + 1, &state);
        state_fresh = true;
        last_ingest_wall = now;
        last_stub_ns = now;
      }
    }

    if (ingest_timeout_ms != 0 && state.valid && last_ingest_wall != 0) {
      const bool stale =
          now - last_ingest_wall >=
          static_cast<std::uint64_t>(ingest_timeout_ms) * 1000000ULL;
      if (stale && !ingest_stale) {
        gf_ara::log::Logger::Instance().Warn(
            "gw",
            "ingest timeout " + std::to_string(ingest_timeout_ms) +
                "ms (10× period) — hold-last Ego/In, speed=0 with fresh ingest is OK");
      }
      ingest_stale = stale;
    }

    if (!state.valid) {
      continue;
    }

    if (PeriodDue(last_ego_pub_ns, ego_period_ms, now)) {
      publish_ego(now);
    }
    if (PeriodDue(last_in_pub_ns, in_period_ms, now)) {
      publish_in(now);
    }

    // Pure forward: apply valid ParkingTrajectory if present, else Trajectory.
    // EM DriveParkFG set-diff keeps only one planner process alive.
    bool applied = false;
    auto park_taken = park_traj_sub.Take();
    auto drive_taken = traj_sub.Take();

    if (park_taken && park_taken.Value().has_value() && park_taken.Value()->valid) {
      const auto& p = *park_taken.Value();
      ++got_traj;
      rx_traj.Observe(static_cast<std::uint64_t>(got_traj), p.timestamp_ns);
      last_ctrl.throttle = 0.0f;
      last_ctrl.brake = 0.15f;
      last_ctrl.steer = 0.0f;
      if (p.n_points >= 2) {
        const float dx = p.x_m[1] - p.x_m[0];
        const float dy = p.y_m[1] - p.y_m[0];
        last_ctrl.steer = std::atan2(dy, dx + 1e-3f);
      }
      last_ctrl.target_speed_mps = 0.0f;
      last_ctrl.ctrl_mode = 0;
      last_ctrl.has = true;
      last_lane = "parking";
      applied = true;
    } else if (drive_taken && drive_taken.Value().has_value()) {
      const auto& t = *drive_taken.Value();
      ++got_traj;
      rx_traj.Observe(static_cast<std::uint64_t>(got_traj), t.timestamp_ns);
      last_ctrl.throttle = t.throttle;
      last_ctrl.brake = t.brake;
      last_ctrl.steer = t.steer;
      last_ctrl.target_speed_mps = t.target_speed_mps;
      last_ctrl.ctrl_mode = t.ctrl_mode;
      last_ctrl.has = true;
      float y_end = 0.0f;
      const char* lane = last_lane.c_str();
      if (t.point_count > 0) {
        y_end = t.points_y_m[t.point_count - 1];
        lane = LaneFromYEnd(y_end);
        last_lane = lane;
      }
      applied = true;
    }

    if (applied) {
      publish_cmd();
      if (max_traj > 0 && got_traj >= max_traj) {
        std::cout << "gf-vehicle-can-gateway: received " << got_traj
                  << " selected traj sample(s), exiting OK\n";
        period_timer.Stop();
        waitset.MarkForDestruction();
        if (cmd_ch) {
          gf_channel_close(cmd_ch);
        }
        if (state_ch) {
          gf_channel_close(state_ch);
        }
        if (hint_ch) {
          gf_channel_close(hint_ch);
        }
        return EXIT_SUCCESS;
      }
    } else if (PeriodDue(last_cmd_pub_ns, cmd_period_ms, now)) {
      publish_cmd();
    }
  }

  period_timer.Stop();
  waitset.MarkForDestruction();
  if (cmd_ch) {
    gf_channel_close(cmd_ch);
  }
  if (state_ch) {
    gf_channel_close(state_ch);
  }
  if (hint_ch) {
    gf_channel_close(hint_ch);
  }
  return EXIT_SUCCESS;
}
