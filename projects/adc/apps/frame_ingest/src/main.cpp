// gf_frame_ingest — Create GfChannel slots; exec independent C++ modules (no Python).

#include "gf_gen/frame_ingest_config.hpp"
#include "gf_channel/gf_channel.h"
#include "gf_channel/boundary_pods.h"

#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

#include <signal.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

namespace {

volatile sig_atomic_t g_stop = 0;
void OnSig(int) { g_stop = 1; }

void SetEnv(const char* key, const char* val) {
  if (key && val) {
    ::setenv(key, val, 1);
  }
}

const char* EnvOr(const char* key, const char* fallback) {
  const char* v = std::getenv(key);
  return (v && v[0]) ? v : fallback;
}

std::string ResolveFrameSource() {
  const char* freeze = gf_gen::frame_ingest::kActiveSource;
  std::string s = EnvOr("GF_FRAME_SOURCE", EnvOr("GF_ACTIVE_SOURCE", freeze));
  if (s == "synth") {
    s = "colorbar";
  }
  if (s == "file") {
    s = "replay";
  }
  if (s == "carla_file") {
    s = "carla";
  }
  return s;
}

std::string FindBin(const char* name) {
  // Staged runtime only — no apps/* tree archaeology.
  if (const char* rt = std::getenv("GF_RUNTIME_DIR"); rt && rt[0]) {
    std::string p = std::string(rt) + "/bin/" + name;
    if (::access(p.c_str(), X_OK) == 0) {
      return p;
    }
  }
  if (const char* e = std::getenv("GF_BUILD_DIR"); e && e[0]) {
    std::string p = std::string(e) + "/runtime/bin/" + name;
    if (::access(p.c_str(), X_OK) == 0) {
      return p;
    }
  }
  return name;  // PATH
}

const char* ModuleBinary(const std::string& src) {
  if (src == "colorbar") {
    return "gf_frame_colorbar";
  }
  if (src == "replay") {
    return "gf_frame_replay";
  }
  if (src == "carla") {
    return "gf_carla_io";
  }
  if (src == "isp") {
    return nullptr;  // handled in-process stub
  }
  return nullptr;
}

}  // namespace

int main(int /*argc*/, char** /*argv*/) {
  using namespace gf_gen::frame_ingest;

  const std::string frame_src = ResolveFrameSource();
  if (!kBridgeEnabled || frame_src == "none") {
    std::cout << "[gf_frame_ingest] disabled — exit 0\n";
    return 0;
  }

  signal(SIGINT, OnSig);
  signal(SIGTERM, OnSig);

  SetEnv("GF_FRAME_SOURCE", frame_src.c_str());
  SetEnv("GF_ACTIVE_SOURCE", frame_src.c_str());
  SetEnv("GF_PIXEL_FORMAT", kPixelFormat);
  SetEnv("GF_EGO_SOURCE", kEgoSource);
  SetEnv("GF_CHANNEL_TRANSPORT", "shm");
  SetEnv("GF_CAMERA_SLOT", kCameraSlotFront);
  SetEnv("GF_VEHICLE_STATE_SLOT", kVehicleStateSlot);
  SetEnv("GF_VEHICLE_CMD_SLOT", kVehicleCmdSlot);
  SetEnv("GF_FAKE_PERC_SLOT", kFakePercSlot);
  {
    char buf[64];
    std::snprintf(buf, sizeof(buf), "%u", static_cast<unsigned>(kFrameW));
    SetEnv("GF_CARLA_CAM_W", buf);
    std::snprintf(buf, sizeof(buf), "%u", static_cast<unsigned>(kFrameH));
    SetEnv("GF_CARLA_CAM_H", buf);
  }
  SetEnv("GF_CHANNEL_INGEST_OWNER", "cpp");

  std::vector<GfChannel*> channels;
  for (std::uint32_t i = 0; i < kCameraSlotCount; ++i) {
    const auto& s = kCameraSlots[i];
    GfChannel* ch = gf_channel_create(s.slot_name, s.w, s.h,
                                      gf_channel_format_from_name(s.pixel_format), s.buffers);
    if (!ch) {
      std::cerr << "[ERROR] frame_ingest: create camera " << s.slot_name << " failed\n";
      for (auto* c : channels) {
        gf_channel_close(c);
      }
      return 2;
    }
    std::cout << "[gf_frame_ingest] GfChannel created " << s.slot_name << "\n";
    channels.push_back(ch);
  }

  if (frame_src == "isp") {
    std::cout << "[gf_frame_ingest] module=isp (board path / SIL stub — slots held empty)\n";
    while (!g_stop) {
      ::usleep(200000);
    }
    for (auto* c : channels) {
      gf_channel_close(c);
    }
    return 0;
  }

  const char* mod = ModuleBinary(frame_src);
  if (!mod) {
    std::cerr << "[ERROR] frame_ingest: unknown source=" << frame_src << "\n";
    for (auto* c : channels) {
      gf_channel_close(c);
    }
    return 2;
  }
  const std::string bin = FindBin(mod);
  std::cout << "[gf_frame_ingest] exec module source=" << frame_src << " bin=" << bin << "\n";

  const pid_t child = ::fork();
  if (child < 0) {
    std::cerr << "[ERROR] frame_ingest: fork failed\n";
    for (auto* c : channels) {
      gf_channel_close(c);
    }
    return 2;
  }
  if (child == 0) {
    execl(bin.c_str(), mod, static_cast<char*>(nullptr));
    // try PATH
    execlp(mod, mod, static_cast<char*>(nullptr));
    std::cerr << "[ERROR] frame_ingest: exec " << mod << " failed errno=" << errno << "\n";
    _exit(127);
  }

  int status = 0;
  while (!g_stop) {
    const pid_t r = ::waitpid(child, &status, WNOHANG);
    if (r == child) {
      break;
    }
    if (r < 0 && errno != EINTR) {
      break;
    }
    ::usleep(100000);
  }
  if (g_stop) {
    ::kill(child, SIGTERM);
    ::waitpid(child, &status, 0);
  }
  for (auto* c : channels) {
    gf_channel_close(c);
  }
  if (WIFEXITED(status)) {
    return WEXITSTATUS(status);
  }
  return 1;
}
