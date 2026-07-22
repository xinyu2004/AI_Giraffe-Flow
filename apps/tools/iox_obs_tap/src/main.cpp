// P2.5: iceoryx observability tap — subscribe allowlisted services → NDJSON stdout.
// Pipe into: GMT bridge foxglove --ws --stdin
//
// Env GF_OBS_LIVE_SERVICES: comma-separated short names (default: EgoMotion,Trajectory).
// Only services implemented below are honored; others are warned on stderr.

#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_gen/proxy/ego_motion_proxy.hpp"
#include "gf_gen/proxy/trajectory_proxy.hpp"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <set>
#include <string>
#include <thread>
#include <vector>

namespace {

constexpr int kMaxPointsExport = 16;

std::uint64_t now_ns() {
  return static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(
          std::chrono::steady_clock::now().time_since_epoch())
          .count());
}

std::set<std::string> parse_allowlist() {
  const char* env = std::getenv("GF_OBS_LIVE_SERVICES");
  std::string raw = env && *env ? env : "EgoMotion,Trajectory";
  std::set<std::string> out;
  std::string cur;
  for (char c : raw) {
    if (c == ',' || c == ';' || c == ' ') {
      if (!cur.empty()) {
        // strip services.semantic. prefix if present
        const std::string pref = "services.semantic.";
        if (cur.rfind(pref, 0) == 0) {
          cur = cur.substr(pref.size());
        }
        out.insert(cur);
        cur.clear();
      }
    } else {
      cur.push_back(c);
    }
  }
  if (!cur.empty()) {
    const std::string pref = "services.semantic.";
    if (cur.rfind(pref, 0) == 0) {
      cur = cur.substr(pref.size());
    }
    out.insert(cur);
  }
  return out;
}

void emit_ego(const gf_gen::EgoMotion& ego) {
  const std::uint64_t t_ns = ego.timestamp_ns ? ego.timestamp_ns : now_ns();
  std::printf(
      "{\"t_ns\":%llu,\"topic\":\"/gf/EgoMotion\",\"data\":{"
      "\"timestamp_ns\":%llu,\"speed_mps\":%.6g,\"yaw_rate_degps\":%.6g,"
      "\"steer_angle_deg\":%.6g,\"gear\":%u}}\n",
      static_cast<unsigned long long>(t_ns),
      static_cast<unsigned long long>(ego.timestamp_ns),
      static_cast<double>(ego.speed_mps),
      static_cast<double>(ego.yaw_rate_degps),
      static_cast<double>(ego.steer_angle_deg),
      static_cast<unsigned>(ego.gear));
  std::fflush(stdout);
}

void emit_traj(const gf_gen::Trajectory& t) {
  const std::uint64_t t_ns = t.timestamp_ns ? t.timestamp_ns : now_ns();
  const int n = static_cast<int>(t.point_count);
  const int export_n = n < kMaxPointsExport ? n : kMaxPointsExport;

  std::string xs;
  std::string ys;
  for (int i = 0; i < export_n; ++i) {
    if (i) {
      xs += ',';
      ys += ',';
    }
    char buf[64];
    std::snprintf(buf, sizeof(buf), "%.6g", static_cast<double>(t.points_x_m[i]));
    xs += buf;
    std::snprintf(buf, sizeof(buf), "%.6g", static_cast<double>(t.points_y_m[i]));
    ys += buf;
  }

  std::printf(
      "{\"t_ns\":%llu,\"topic\":\"/gf/Trajectory\",\"data\":{"
      "\"timestamp_ns\":%llu,\"point_count\":%u,"
      "\"points_x_m\":[%s],\"points_y_m\":[%s],"
      "\"gear_shift_first\":%u,\"gear_shift_second\":%u}}\n",
      static_cast<unsigned long long>(t_ns),
      static_cast<unsigned long long>(t.timestamp_ns),
      static_cast<unsigned>(t.point_count),
      xs.c_str(),
      ys.c_str(),
      static_cast<unsigned>(t.gear_shift_first),
      static_cast<unsigned>(t.gear_shift_second));
  std::fflush(stdout);
}

}  // namespace

int main() {
  const auto allow = parse_allowlist();
  const bool want_ego = allow.count("EgoMotion") > 0;
  const bool want_traj = allow.count("Trajectory") > 0;

  for (const auto& s : allow) {
    if (s != "EgoMotion" && s != "Trajectory") {
      std::cerr << "gf-iox-obs-tap: ignore unsupported service '" << s
                << "' (implemented: EgoMotion, Trajectory)\n";
    }
  }
  if (!want_ego && !want_traj) {
    std::cerr << "gf-iox-obs-tap: empty/unsupported GF_OBS_LIVE_SERVICES — nothing to do\n";
    return EXIT_FAILURE;
  }

  gf_ara::com::binding::iceoryx::InitRuntime("gf-iox-obs-tap");

  gf_gen::EgoMotionProxy ego_sub{};
  gf_gen::TrajectoryProxy traj_sub{};

  std::cerr << "gf-iox-obs-tap: start allowlist=";
  for (const auto& s : allow) {
    std::cerr << s << ",";
  }
  std::cerr << " → NDJSON stdout\n";

  while (!iox::posix::hasTerminationRequested()) {
    if (want_ego) {
      auto ego_taken = ego_sub.Take();
      if (ego_taken && ego_taken.Value().has_value()) {
        emit_ego(*ego_taken.Value());
      }
    }
    if (want_traj) {
      auto traj_taken = traj_sub.Take();
      if (traj_taken && traj_taken.Value().has_value()) {
        emit_traj(*traj_taken.Value());
      }
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }
  return 0;
}
