// Host-only Foxglove BEV: stdin NDJSON → gf_foxglove_core paint → WebSocket.
// No iceoryx / RouDi. Used by carla_scenarios/octave_bridge BevFeed.

#include "gf_foxglove/bev_compose.hpp"
#include "gf_foxglove/bev_ndjson.hpp"
#include "gf_foxglove/ws_hub.hpp"

#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace {

std::atomic<bool> g_stop{false};

std::uint64_t now_ns() {
  return static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(
          std::chrono::system_clock::now().time_since_epoch())
          .count());
}

void on_sig(int) { g_stop.store(true); }

}  // namespace

int main(int argc, char** argv) {
  const char* host = "0.0.0.0";
  std::uint16_t port = 8765;
  int period_ms = 33;
  for (int i = 1; i < argc; ++i) {
    if (std::strcmp(argv[i], "--host") == 0 && i + 1 < argc) {
      host = argv[++i];
    } else if (std::strcmp(argv[i], "--port") == 0 && i + 1 < argc) {
      port = static_cast<std::uint16_t>(std::atoi(argv[++i]));
    } else if (std::strcmp(argv[i], "--period-ms") == 0 && i + 1 < argc) {
      period_ms = std::max(1, std::atoi(argv[++i]));
    } else if (std::strcmp(argv[i], "--help") == 0 || std::strcmp(argv[i], "-h") == 0) {
      std::cerr << "gf_host_bev_ws [--host 0.0.0.0] [--port 8765] [--period-ms 33]\n"
                   "  stdin: NDJSON lines {\"topic\":\"/gf/…\",\"t_ns\":…,\"data\":{…}}\n";
      return 0;
    }
  }

  std::signal(SIGINT, on_sig);
  std::signal(SIGTERM, on_sig);

  gf_foxglove::WsHub hub;
  hub.set_name("gf_host_bev_ws");
  if (!hub.listen(host, port)) {
    std::cerr << "gf_host_bev_ws: listen failed\n";
    return EXIT_FAILURE;
  }
  const std::vector<std::string> topics{"/gf/driving/bev/compressed", "/gf/EgoMotion",
                                        "/gf/Trajectory",
                                        "/gf/Perception_MESSAGE_Out_St"};
  hub.advertise(topics);
  std::cerr << "gf_host_bev_ws: " << hub.bind_desc()
            << " paint every " << period_ms << "ms (stdin NDJSON)\n";

  gf_foxglove::LiveBevState bev;
  std::mutex mu;
  std::thread reader([&] {
    std::string line;
    while (!g_stop.load()) {
      if (!std::getline(std::cin, line)) {
        g_stop.store(true);
        break;
      }
      if (line.empty()) continue;
      std::lock_guard<std::mutex> lock(mu);
      gf_foxglove::apply_ndjson_row(bev, line);
    }
  });

  auto last = std::chrono::steady_clock::now();
  while (!g_stop.load()) {
    hub.poll();
    const auto now = std::chrono::steady_clock::now();
    if (now - last >= std::chrono::milliseconds(period_ms)) {
      last = now;
      gf_foxglove::LiveBevState snap;
      {
        std::lock_guard<std::mutex> lock(mu);
        snap = bev;
      }
      const auto png = gf_foxglove::render_ego_bev_png(snap);
      const std::uint64_t t = snap.t_ns ? snap.t_ns : now_ns();
      hub.publish_json("/gf/driving/bev/compressed", t,
                       gf_foxglove::compressed_image_json(t, png, "front"));
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
  }
  if (reader.joinable()) reader.join();
  return 0;
}
