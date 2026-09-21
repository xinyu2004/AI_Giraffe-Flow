#pragma once

// BEV observer mount loader ONLY (paint / Foxglove).
// Product envelope constants (7 / 35 / fov) are frozen in fs_envelope_cal.hpp
// at gf-config/compose time — not re-derived here each run.
//
// Files (iox_obs_foxglove tree — NOT carla_scenarios):
//   tools/gmt_board/iox_obs_foxglove/adc/bev.mount.json
//   tools/gmt_board/iox_obs_foxglove/afc/bev.mount.json
// Legacy fallback: config/{adc,afc}/bev.mount.json
// Env: GF_MOUNTS_JSON, or GF_BEV_SKU=afc|adc to pick default path.
// CARLA spectator mounts live under carla_scenarios/config/spectator/ (env 1–4).

#include "fs_envelope/fs_envelope_cal.hpp"

#include <cstring>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <string>

namespace gf_fs_envelope {

struct CamMount {
  float x{0.0f};
  float y{0.0f};
  float z{1.2f};
  float pitch_deg{-5.0f};
  float yaw_deg{0.0f};
  float roll_deg{0.0f};
  float fov_deg{100.0f};
  float w{640.0f};
  float h{480.0f};
  float look_x{40.0f};
  float oy_ego_frac{0.62f};
  float y_far_px{28.0f};
};

inline CamMount DefaultBevMountAdc() {
  // Oblique ADC observer (match config/adc/bev.mount.json + CARLA bev_adc).
  return {-45.0f, 0.0f, 48.0f, -29.5f, 0.0f, 0.0f, 60.0f, 400.0f, 800.0f, 40.0f, 0.62f, 28.0f};
}

inline CamMount DefaultBevMountAfc() {
  // Legacy AFC paint: CamBack=35, Height=40, Look=60; ego near bottom (oy = H-44).
  return {-35.0f, 0.0f, 40.0f, -28.0f, 0.0f, 0.0f, 60.0f, 400.0f, 800.0f, 60.0f, -1.0f,
          32.0f};
}

inline bool ParseFloatAfterKey(const std::string& body, const char* key, float* out) {
  const std::string pat = std::string("\"") + key + "\"";
  const auto p = body.find(pat);
  if (p == std::string::npos) {
    return false;
  }
  const auto colon = body.find(':', p + pat.size());
  if (colon == std::string::npos) {
    return false;
  }
  char* end = nullptr;
  const float v = std::strtof(body.c_str() + colon + 1, &end);
  if (end == body.c_str() + colon + 1) {
    return false;
  }
  *out = v;
  return true;
}

inline bool ExtractObjectAfterKey(const std::string& json, const char* key, std::string* obj) {
  const std::string pat = std::string("\"") + key + "\"";
  auto p = json.find(pat);
  if (p == std::string::npos) {
    return false;
  }
  p = json.find('{', p);
  if (p == std::string::npos) {
    return false;
  }
  int depth = 0;
  for (size_t i = p; i < json.size(); ++i) {
    if (json[i] == '{') {
      ++depth;
    } else if (json[i] == '}') {
      --depth;
      if (depth == 0) {
        *obj = json.substr(p, i - p + 1);
        return true;
      }
    }
  }
  return false;
}

inline void FillMountFromObject(const std::string& obj, CamMount* m) {
  float v = 0.0f;
  if (ParseFloatAfterKey(obj, "x", &v)) m->x = v;
  if (ParseFloatAfterKey(obj, "y", &v)) m->y = v;
  if (ParseFloatAfterKey(obj, "z", &v)) m->z = v;
  if (ParseFloatAfterKey(obj, "pitch", &v)) m->pitch_deg = v;
  if (ParseFloatAfterKey(obj, "yaw", &v)) m->yaw_deg = v;
  if (ParseFloatAfterKey(obj, "roll", &v)) m->roll_deg = v;
  if (ParseFloatAfterKey(obj, "fov", &v)) m->fov_deg = v;
  if (ParseFloatAfterKey(obj, "w", &v)) m->w = v;
  if (ParseFloatAfterKey(obj, "h", &v)) m->h = v;
  if (ParseFloatAfterKey(obj, "look_x", &v)) m->look_x = v;
  if (ParseFloatAfterKey(obj, "oy_ego_frac", &v)) m->oy_ego_frac = v;
  if (ParseFloatAfterKey(obj, "y_far_px", &v)) m->y_far_px = v;
}

inline bool LoadBevMountJson(const std::string& path, CamMount* out) {
  if (!out) {
    return false;
  }
  std::ifstream in(path);
  if (!in) {
    return false;
  }
  std::ostringstream ss;
  ss << in.rdbuf();
  const std::string json = ss.str();
  std::string obj;
  // Prefer "bev" key; accept root object if file is only bev fields.
  if (!ExtractObjectAfterKey(json, "bev", &obj)) {
    if (json.find('\"') != std::string::npos && json.find('{') != std::string::npos) {
      obj = json;
    } else {
      return false;
    }
  }
  FillMountFromObject(obj, out);
  return true;
}

inline bool BevSkuIsAdc() {
  if (const char* v = std::getenv("GF_BEV_SKU")) {
    if (v[0] == 'a' || v[0] == 'A') {
      if (v[1] == 'd' || v[1] == 'D') {
        return true;
      }
      if (v[1] == 'f' || v[1] == 'F') {
        return false;
      }
    }
  }
  if (const char* p = std::getenv("GF_PROJECT_DIR")) {
    return std::strstr(p, "/adc") != nullptr || std::strstr(p, "\\adc") != nullptr;
  }
  return false;
}

inline bool PathLooksAdc(const char* p) {
  return std::strstr(p, "/adc/") != nullptr || std::strstr(p, "adc/bev.mount") != nullptr ||
         std::strstr(p, "/config/adc/") != nullptr;
}

inline CamMount& BevMountStorage() {
  static CamMount m = DefaultBevMountAdc();
  static bool inited = false;
  if (!inited) {
    inited = true;
    m = BevSkuIsAdc() ? DefaultBevMountAdc() : DefaultBevMountAfc();
    if (const char* e = std::getenv("GF_MOUNTS_JSON")) {
      if (e[0]) {
        CamMount loaded = m;
        if (LoadBevMountJson(e, &loaded)) {
          m = loaded;
          return m;
        }
      }
    }
    const char* path = BevSkuIsAdc()
                           ? "tools/gmt_board/iox_obs_foxglove/adc/bev.mount.json"
                           : "tools/gmt_board/iox_obs_foxglove/afc/bev.mount.json";
    static const char* kPrefs[] = {
        path,
        "tools/gmt_board/iox_obs_foxglove/adc/bev.mount.json",
        "tools/gmt_board/iox_obs_foxglove/afc/bev.mount.json",
        "tools/gmt_board/iox_obs_foxglove/config/adc/bev.mount.json",
        "tools/gmt_board/iox_obs_foxglove/config/afc/bev.mount.json",
        "../tools/gmt_board/iox_obs_foxglove/adc/bev.mount.json",
        "../tools/gmt_board/iox_obs_foxglove/afc/bev.mount.json",
        "../../tools/gmt_board/iox_obs_foxglove/adc/bev.mount.json",
        "../../tools/gmt_board/iox_obs_foxglove/afc/bev.mount.json",
        "../../../tools/gmt_board/iox_obs_foxglove/adc/bev.mount.json",
        "../../../tools/gmt_board/iox_obs_foxglove/afc/bev.mount.json",
    };
    for (const char* p : kPrefs) {
      CamMount loaded = m;
      if (LoadBevMountJson(p, &loaded)) {
        if (BevSkuIsAdc() == PathLooksAdc(p)) {
          m = loaded;
          break;
        }
        m = loaded;
      }
    }
  }
  return m;
}

inline const CamMount& BevMount() { return BevMountStorage(); }

/** Optional: load bev mount at process start (paint / obs). No envelope derive. */
inline void InitBevMountFromFile() { (void)BevMount(); }

// ---- Compat shims (envelope = frozen cal constants; no runtime derive) ----

inline void InitEnvelopeFromMounts() {
  InitBevMountFromFile();
}

inline float SideLatM() { return kFsSideCapM; }
inline float RearCapM() { return kFsRearCapM; }
inline float FrontFovDeg() { return kFsFrontFovDeg; }
inline float RearFovDeg() { return kFsRearFovDeg; }

inline const CamMount& FrontMount() {
  // Product front = camera_contract / compose; stub matches ADC/AFC front 3MP.
  static CamMount front{0.55f, 0.0f, 1.35f, -5.0f, 0.0f, 0.0f, 100.0f, 2048.0f, 1536.0f,
                        40.0f, 0.62f, 28.0f};
  return front;
}

}  // namespace gf_fs_envelope
