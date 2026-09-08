// Fallback Foxglove WS (EgoMotion + Trajectory only). Prefer codegen:
//   gf-codegen generate → ${GF_GENERATED_DIR}/src/obs_foxglove_main.cpp

#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_foxglove/bev_compose.hpp"
#include "gf_foxglove/bev_ingest.hpp"
#include "gf_foxglove/camera.hpp"
#include "gf_foxglove/ws_hub.hpp"
#include "gf_gen/proxy/ego_motion_proxy.hpp"
#include "gf_gen/proxy/trajectory_proxy.hpp"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

namespace {

std::uint64_t now_ns() {
  return static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(
          std::chrono::system_clock::now().time_since_epoch())
          .count());
}

int env_int(const char* k, int def) {
  const char* v = std::getenv(k);
  if (!v || !*v) return def;
  return std::atoi(v);
}

bool env_on(const char* k, bool def) {
  const char* v = std::getenv(k);
  if (!v || !*v) return def;
  return !(v[0] == '0' && v[1] == '\0');
}

}  // namespace

int main() {
  const char* host = std::getenv("GF_WS_HOST");
  if (!host || !*host) host = "0.0.0.0";
  const std::uint16_t port = static_cast<std::uint16_t>(env_int("GF_WS_PORT", 8765));
  const bool synth_bev = env_on("GF_SYNTH_BEV", true);
  const bool cam_on = env_on("GF_CAMERA_PUBLISH", true);

  gf_foxglove::WsHub hub;
  if (!hub.listen(host, port)) return EXIT_FAILURE;

  std::vector<std::string> topics{"/gf/EgoMotion", "/gf/Trajectory"};
  if (synth_bev) topics.push_back("/gf/driving/bev/compressed");
  if (cam_on) topics.push_back("/gf/driving/camera/front/compressed");
  hub.advertise(topics);

  gf_ara::com::binding::iceoryx::InitRuntime("gf-foxglove-ws");
  gf_gen::EgoMotionProxy sub_ego{};
  gf_gen::TrajectoryProxy sub_traj{};

  gf_foxglove::LiveBevState bev;
  const char* slot = std::getenv("GF_CAMERA_SLOT");
  const char* frame = std::getenv("GF_CAMERA_FRAME");
  gf_foxglove::CameraPub cam(slot && *slot ? slot : "gf.channel.front",
                             frame && *frame ? frame : "");

  std::cerr << "gf-foxglove-ws: fallback Ego+Traj (codegen missing)\n";
  auto last_bev = std::chrono::steady_clock::now();

  while (!iox::posix::hasTerminationRequested()) {
    hub.poll();
    auto taken_e = sub_ego.Take();
    if (taken_e && taken_e.Value().has_value()) {
      const auto& s = *taken_e.Value();
      const std::uint64_t t = s.timestamp_ns ? s.timestamp_ns : now_ns();
      char js[256];
      std::snprintf(js, sizeof(js),
                    "{\"timestamp_ns\":%llu,\"speed_mps\":%.6g,\"yaw_rate_degps\":%.6g,"
                    "\"steer_angle_deg\":%.6g,\"gear\":%u}",
                    static_cast<unsigned long long>(s.timestamp_ns),
                    static_cast<double>(s.speed_mps), static_cast<double>(s.yaw_rate_degps),
                    static_cast<double>(s.steer_angle_deg), static_cast<unsigned>(s.gear));
      hub.publish_json("/gf/EgoMotion", t, js);
      gf_foxglove::apply_sample(bev, "EgoMotion", &s);
    }
    auto taken_t = sub_traj.Take();
    if (taken_t && taken_t.Value().has_value()) {
      const auto& s = *taken_t.Value();
      gf_foxglove::apply_sample(bev, "Trajectory", &s);
      const std::uint64_t t = s.timestamp_ns ? s.timestamp_ns : now_ns();
      std::string js = "{\"timestamp_ns\":";
      js += std::to_string(s.timestamp_ns);
      js += ",\"point_count\":";
      js += std::to_string(static_cast<unsigned>(s.point_count));
      js += "}";
      hub.publish_json("/gf/Trajectory", t, js);
    }
    const auto now = std::chrono::steady_clock::now();
    if (synth_bev && now - last_bev >= std::chrono::milliseconds(33)) {
      last_bev = now;
      const auto png = gf_foxglove::render_ego_bev_png(bev);
      const std::uint64_t t = bev.t_ns ? bev.t_ns : now_ns();
      hub.publish_json("/gf/driving/bev/compressed", t,
                       gf_foxglove::compressed_image_json(t, png, "front"));
    }
    if (cam_on) {
      std::uint64_t t = 0;
      const std::string img = cam.poll(&t);
      if (!img.empty()) hub.publish_json("/gf/driving/camera/front/compressed", t, img);
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }
  return 0;
}
