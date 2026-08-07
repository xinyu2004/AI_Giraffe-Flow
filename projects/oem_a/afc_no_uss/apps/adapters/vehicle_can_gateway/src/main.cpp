#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_ara/runtime/process_bringup.hpp"
#include "gf_gen/proxy/trajectory_proxy.hpp"
#include "gf_gen/skeleton/ego_motion_skeleton.hpp"
#include "gf_gen/skeleton/perception__in__st_skeleton.hpp"

#if __has_include("gf_gen/frame_ingest_config.hpp")
#include "gf_gen/frame_ingest_config.hpp"
#define GF_GW_HAS_FRAME_INGEST 1
#endif

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <string>
#include <thread>

namespace {

constexpr const char* kProcess = "adapter.vehicle_can_gateway";

std::uint64_t now_ns() {
  return static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(
          std::chrono::steady_clock::now().time_since_epoch())
          .count());
}

const char* LaneFromYEnd(float y_end) {
  // Ego-frame: +y left (planning FillCurvedTrajectory). Thresholds tuned for
  // demo arcs (~0.5 m); demo LC can override.
  if (y_end > 0.4f) {
    return "left";
  }
  if (y_end < -0.4f) {
    return "right";
  }
  return "none";
}

void WriteCarlaCmd(const std::string& path,
                   const char* lane,
                   float speed_mps,
                   std::uint64_t seq) {
  if (path.empty()) {
    return;
  }
  const std::string tmp = path + ".tmp";
  {
    std::ofstream out(tmp, std::ios::trunc);
    if (!out) {
      return;
    }
    out << "{\"lane_change\":\"" << lane << "\",\"speed_mps\":" << speed_mps
        << ",\"seq\":" << seq << ",\"timestamp_ns\":" << now_ns() << "}\n";
  }
  if (std::rename(tmp.c_str(), path.c_str()) != 0) {
    std::remove(tmp.c_str());
  }
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
    return EXIT_FAILURE;
  }

  // Compile-time freeze (req.frame_ingest); env overrides for debug only.
  const char* cmd_env = std::getenv("GF_CARLA_CMD_PATH");
  std::string cmd_path = (cmd_env && cmd_env[0]) ? cmd_env : "";
#if defined(GF_GW_HAS_FRAME_INGEST)
  if (cmd_path.empty() && gf_gen::frame_ingest::kBridgeEnabled) {
    cmd_path = gf_gen::frame_ingest::kCmdPath;
  }
  const bool demo_lc = [] {
    const char* v = std::getenv("GF_CARLA_DEMO_LC");
    if (v && v[0]) {
      return v[0] == '1';
    }
    return gf_gen::frame_ingest::kDemoLaneChange;
  }();
  const std::uint32_t demo_sec = [] {
    const char* v = std::getenv("GF_CARLA_DEMO_LC_SEC");
    if (v && v[0]) {
      return static_cast<std::uint32_t>(std::strtoul(v, nullptr, 10));
    }
    return gf_gen::frame_ingest::kDemoLaneChangeSec;
  }();
#else
  const bool demo_lc = [] {
    const char* v = std::getenv("GF_CARLA_DEMO_LC");
    return v && v[0] == '1';
  }();
  const std::uint32_t demo_sec = [] {
    const char* v = std::getenv("GF_CARLA_DEMO_LC_SEC");
    if (!v || !v[0]) {
      return 8u;
    }
    return static_cast<std::uint32_t>(std::strtoul(v, nullptr, 10));
  }();
#endif
  const char* demo_dir_env = std::getenv("GF_CARLA_DEMO_LC_DIR");
  const char* demo_dir =
      (demo_dir_env && demo_dir_env[0]) ? demo_dir_env : "left";

  gf_gen::EgoMotionSkeleton ego_pub{};
  gf_gen::Perception_In_StSkeleton perc_in_pub{};
  gf_gen::TrajectoryProxy traj_sub{};

  std::uint64_t frame = 0;
  int got_traj = 0;
  std::uint64_t cmd_seq = 0;
  std::string last_lane = "none";
  const auto t0 = std::chrono::steady_clock::now();
  bool demo_fired = false;

  std::cout << "gf-vehicle-can-gateway: start";
  if (max_traj > 0) {
    std::cout << " (exit after " << max_traj << " Trajectory)";
  }
  if (!cmd_path.empty()) {
    std::cout << " carla_cmd=" << cmd_path;
    if (demo_lc) {
      std::cout << " demo_lc=" << demo_dir << "@" << demo_sec << "s";
    }
  }
  std::cout << std::endl;

  while (!iox::posix::hasTerminationRequested()) {
    supervisor.Tick();
    if (supervisor.ExitForEmRestart()) {
      return gf_ara::exec::kEmRestartExitCode;
    }

    gf_gen::EgoMotion ego{};
    ego.timestamp_ns = now_ns();
    ego.speed_mps = 5.0f + static_cast<float>(frame % 10) * 0.1f;
    ego.yaw_rate_degps = 0.1f;
    ego.steer_angle_deg = 2.0f;
    ego.gear = 4;
    (void)ego_pub.Send(ego);

    gf_gen::Perception_In_St pin{};
    pin.timestamp_ns = ego.timestamp_ns;
    pin.ipc_frame_counter = static_cast<std::uint32_t>(frame);
    pin.gear = ego.gear;
    pin.vehicle_speed = ego.speed_mps;
    pin.yaw_rate = ego.yaw_rate_degps;
    pin._vendor_payload_opaque[0] = 0;
    (void)perc_in_pub.Send(pin);

    const char* lane = "none";
    float y_end = 0.0f;
    auto taken = traj_sub.Take();
    if (taken && taken.Value().has_value()) {
      const auto& t = *taken.Value();
      ++got_traj;
      if (t.point_count > 0) {
        y_end = t.points_y_m[t.point_count - 1];
        lane = LaneFromYEnd(y_end);
      }
      std::cout << "gf-vehicle-can-gateway: Trajectory#" << got_traj
                << " points=" << static_cast<int>(t.point_count)
                << " y_end=" << y_end << " lane=" << lane
                << " ts_ns=" << t.timestamp_ns << std::endl;
      if (max_traj > 0 && got_traj >= max_traj) {
        std::cout << "gf-vehicle-can-gateway: received " << got_traj
                  << " Trajectory sample(s), exiting OK\n";
        return EXIT_SUCCESS;
      }
    }

    if (!cmd_path.empty()) {
      if (demo_lc && !demo_fired) {
        const auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(
                                 std::chrono::steady_clock::now() - t0)
                                 .count();
        if (elapsed >= static_cast<std::int64_t>(demo_sec)) {
          lane = demo_dir;
          demo_fired = true;
          std::cout << "gf-vehicle-can-gateway: demo_lc force lane_change="
                    << lane << std::endl;
        }
      }
      // Hold demo direction for a few seconds after fire.
      if (demo_fired) {
        const auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(
                                 std::chrono::steady_clock::now() - t0)
                                 .count();
        if (elapsed < static_cast<std::int64_t>(demo_sec) + 3) {
          lane = demo_dir;
        }
      }
      if (lane != last_lane || (got_traj > 0 && (got_traj % 5) == 0)) {
        ++cmd_seq;
        WriteCarlaCmd(cmd_path, lane, ego.speed_mps, cmd_seq);
        if (lane != last_lane) {
          std::cout << "gf-vehicle-can-gateway: wrote carla_cmd seq=" << cmd_seq
                    << " lane_change=" << lane << std::endl;
          last_lane = lane;
        }
      }
    }

    ++frame;
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
  }
  return EXIT_SUCCESS;
}
