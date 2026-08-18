// gf_frame_ingest — Create GfChannel from compile freeze, spawn Python module.
// Config truth: gf_gen/frame_ingest_config.hpp (gf-config → compose). No shell grep.

#include "gf_gen/frame_ingest_config.hpp"
#include "gf_channel/gf_channel.h"

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
  if (!key || !val) {
    return;
  }
  ::setenv(key, val, 1);
}

const char* EnvOr(const char* key, const char* fallback) {
  const char* v = std::getenv(key);
  return (v && v[0]) ? v : fallback;
}

/** Runtime frame module; freeze default is SOP isp. synth → colorbar alias. */
std::string ResolveFrameSource() {
  const char* freeze = gf_gen::frame_ingest::kActiveSource;
  // GF_FRAME_SOURCE primary; GF_TIP_SOURCE / GF_ACTIVE_SOURCE compat aliases.
  std::string s = EnvOr(
      "GF_FRAME_SOURCE",
      EnvOr("GF_TIP_SOURCE", EnvOr("GF_ACTIVE_SOURCE", freeze)));
  if (s == "synth") {
    s = "colorbar";
  }
  if (s == "file") {
    s = "replay";
  }
  // Legacy IPC labels from older freezes / scripts → module names.
  if (s == "carla_file") {
    s = "carla";
  }
  return s;
}

std::string FindModulePy() {
  if (const char* e = std::getenv("GF_FRAME_INGEST_PY"); e && e[0]) {
    return e;
  }
  if (const char* rt = std::getenv("GF_RUNTIME_DIR"); rt && rt[0]) {
    std::string p = std::string(rt) + "/share/frame_ingest/gf_frame_ingest.py";
    if (::access(p.c_str(), R_OK) == 0) {
      return p;
    }
  }
  if (const char* proj = std::getenv("GF_PROJECT_DIR"); proj && proj[0]) {
    std::string p = std::string(proj) + "/apps/frame_ingest/gf_frame_ingest.py";
    if (::access(p.c_str(), R_OK) == 0) {
      return p;
    }
  }
  return {};
}

std::string FindPython() {
  if (const char* e = std::getenv("GF_CARLA_PYTHON"); e && e[0]) {
    return e;
  }
  if (const char* e = std::getenv("GF_PYTHON"); e && e[0]) {
    return e;
  }
  return "python3";
}

uint16_t FormatFromName(const char* name) {
  return gf_channel_format_from_name(name ? name : "nv12");
}

}  // namespace

int main(int /*argc*/, char** /*argv*/) {
  using namespace gf_gen::frame_ingest;

  // Resolve before exporting freeze — GF_FRAME_SOURCE overrides hpp active_source.
  const std::string tip = ResolveFrameSource();

  if (!kBridgeEnabled || tip == "none") {
    std::cout << "[gf_frame_ingest] disabled (kBridgeEnabled="
              << (kBridgeEnabled ? "true" : "false")
              << " frame_source=" << tip << " freeze=" << kActiveSource
              << ") — exit 0\n";
    return 0;
  }

  signal(SIGINT, OnSig);
  signal(SIGTERM, OnSig);

  // Export for Python modules / FCM (resolved module name, not legacy IPC label).
  SetEnv("GF_FRAME_SOURCE", tip.c_str());
  SetEnv("GF_ACTIVE_SOURCE", tip.c_str());
  SetEnv("GF_PIXEL_FORMAT", kPixelFormat);
  SetEnv("GF_EGO_SOURCE", kEgoSource);
  SetEnv("GF_TIP_TRANSPORT", kTipTransport);
  SetEnv("GF_CHANNEL_TRANSPORT", kTipTransport);
  SetEnv("GF_TIP_SLOT", kTipSlotFront);
  SetEnv("GF_CHANNEL_SLOT", kTipSlotFront);
  SetEnv("GF_CARLA_FRAME_PATH", kFramePath);
  SetEnv("GF_CARLA_CMD_PATH", kCmdPath);
  SetEnv("GF_CARLA_EGO_PATH", kEgoPath);
  SetEnv("GF_CARLA_TRUTH_PATH", kTruthPath);
  SetEnv("GF_PLANNING_CTRL_PATH", kCtrlPath);
  {
    char buf[64];
    std::snprintf(buf, sizeof(buf), "%u", static_cast<unsigned>(kFrameW));
    SetEnv("GF_CARLA_CAM_W", buf);
    std::snprintf(buf, sizeof(buf), "%u", static_cast<unsigned>(kFrameH));
    SetEnv("GF_CARLA_CAM_H", buf);
    SetEnv("GF_CAMERA_MOUNT_ID", kMountId);
    SetEnv("GF_CARLA_TIP_MOUNT", kMountId);  // legacy alias
    std::snprintf(buf, sizeof(buf), "%.6f", kMountX);
    SetEnv("GF_CAMERA_MOUNT_X", buf);
    SetEnv("GF_CARLA_TIP_X", buf);
    std::snprintf(buf, sizeof(buf), "%.6f", kMountY);
    SetEnv("GF_CAMERA_MOUNT_Y", buf);
    SetEnv("GF_CARLA_TIP_Y", buf);
    std::snprintf(buf, sizeof(buf), "%.6f", kMountZ);
    SetEnv("GF_CAMERA_MOUNT_Z", buf);
    SetEnv("GF_CARLA_TIP_Z", buf);
    std::snprintf(buf, sizeof(buf), "%.6f", kMountPitch);
    SetEnv("GF_CAMERA_MOUNT_PITCH", buf);
    SetEnv("GF_CARLA_TIP_PITCH", buf);
    std::snprintf(buf, sizeof(buf), "%.6f", kMountYaw);
    SetEnv("GF_CAMERA_MOUNT_YAW", buf);
    SetEnv("GF_CARLA_TIP_YAW", buf);
    std::snprintf(buf, sizeof(buf), "%.6f", kMountRoll);
    SetEnv("GF_CAMERA_MOUNT_ROLL", buf);
    SetEnv("GF_CARLA_TIP_ROLL", buf);
    std::snprintf(buf, sizeof(buf), "%.6f", kMountFov);
    SetEnv("GF_CAMERA_MOUNT_FOV", buf);
    SetEnv("GF_CARLA_TIP_FOV", buf);
  }
  SetEnv("GF_TIP_INGEST_OWNER", "cpp");
  SetEnv("GF_CHANNEL_INGEST_OWNER", "cpp");

  std::vector<GfChannel*> channels;
  channels.reserve(kTipSlotCount);
  for (std::uint32_t i = 0; i < kTipSlotCount; ++i) {
    const auto& s = kTipSlots[i];
    GfChannel* ch = gf_channel_create(s.slot_name, s.w, s.h,
                                     FormatFromName(s.pixel_format), s.buffers);
    if (!ch) {
      std::cerr << "[ERROR] frame_ingest: gf_channel_create failed for " << s.slot_name
                << " errno=" << errno << "\n";
      for (auto* c : channels) {
        gf_channel_close(c);
      }
      return 2;
    }
    std::cout << "[gf_frame_ingest] GfChannel created " << s.slot_name << " "
              << s.w << "x" << s.h << " " << s.pixel_format << "\n";
    channels.push_back(ch);
  }

  const std::string py = FindPython();
  const std::string module = FindModulePy();
  if (module.empty()) {
    std::cerr << "[ERROR] frame_ingest: gf_frame_ingest.py not found "
                 "(set GF_RUNTIME_DIR or GF_PROJECT_DIR / GF_FRAME_INGEST_PY)\n";
    for (auto* c : channels) {
      gf_channel_close(c);
    }
    return 2;
  }

  std::cout << "[gf_frame_ingest] spawn module source=" << tip
            << " (freeze=" << kActiveSource << ") py=" << py << " script=" << module
            << "\n";

  const pid_t child = ::fork();
  if (child < 0) {
    std::cerr << "[ERROR] frame_ingest: fork failed errno=" << errno << "\n";
    for (auto* c : channels) {
      gf_channel_close(c);
    }
    return 2;
  }
  if (child == 0) {
    // Child: module-only (parent owns GfChannel Create).
    execlp(py.c_str(), py.c_str(), module.c_str(), "--module-only", "--source",
           tip.c_str(), static_cast<char*>(nullptr));
    std::cerr << "[ERROR] frame_ingest: execlp failed errno=" << errno << "\n";
    _exit(127);
  }

  int status = 0;
  while (!g_stop) {
    const pid_t r = ::waitpid(child, &status, WNOHANG);
    if (r == child) {
      break;
    }
    if (r < 0 && errno != EINTR) {
      std::cerr << "[ERROR] frame_ingest: waitpid failed errno=" << errno << "\n";
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
    const int code = WEXITSTATUS(status);
    if (code != 0) {
      std::cerr << "[ERROR] frame_ingest: module exited code=" << code
                << " source=" << tip << " (see host_frame_ingest.log)\n";
    }
    return code;
  }
  if (WIFSIGNALED(status)) {
    std::cerr << "[ERROR] frame_ingest: module killed by signal "
              << WTERMSIG(status) << "\n";
  }
  return 1;
}
