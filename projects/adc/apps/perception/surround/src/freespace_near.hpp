#pragma once

// Near-field Empty180 author (SIL: optics caps + occupy). FAPA FSD maps to same shape.

#include "fs_envelope/fs_envelope_cal.hpp"
#include "fs_envelope/fs_mounts.hpp"
#include "fs_envelope/front_optical_footprint.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>

namespace gf_surround {

using gf_fs_envelope::kFsEmptyN;
using gf_fs_envelope::kFsNearFrontCapM;

inline constexpr float kObjHalfW = 0.9f;

enum class FsBoundType : std::uint8_t {
  Unknown = 0,
  Car = 1,
  Bicycle = 2,
  Pedestrian = 3,
  Obstacle = 4,
  Pillar = 5,
  Building = 6,
  Curb = 7,
  Optical = 8,
  LaneBound = 9,
};

struct ObjSample {
  float long_dist_m;
  float lat_dist_m;
  float half_l_m{2.0f};
  float half_w_m{0.9f};
};

inline float WrapPi(float a) {
  constexpr float pi = 3.14159265f;
  constexpr float twopi = 6.2831853f;
  while (a > pi) {
    a -= twopi;
  }
  while (a < -pi) {
    a += twopi;
  }
  return a;
}

inline bool InRearFov(float ang_rad) {
  constexpr float pi = 3.14159265f;
  const float half = 0.5f * gf_fs_envelope::RearFovDeg() * (pi / 180.0f);
  return std::fabs(WrapPi(ang_rad - pi)) <= half;
}

inline bool InFrontFov(float ang_rad) {
  constexpr float pi = 3.14159265f;
  const float half = 0.5f * gf_fs_envelope::FrontFovDeg() * (pi / 180.0f);
  return std::fabs(WrapPi(ang_rad)) <= half;
}

inline float BinAngRad(int i) {
  const float twopi = 6.2831853f;
  return (static_cast<float>(i) + 0.5f) * (twopi / static_cast<float>(kFsEmptyN));
}

inline float BinCapM(int i) {
  const float ang = BinAngRad(i);
  if (InFrontFov(ang)) {
    return kFsNearFrontCapM;
  }
  if (InRearFov(ang)) {
    return gf_fs_envelope::RearCapM();
  }
  const float r = gf_fs_envelope::SurroundSideEmptyR(ang, gf_fs_envelope::SideLatM());
  return (r >= 0.5f) ? r : 0.5f;
}

/** Prefer one-shot fill for Near optical empty (same as planning surround). */
template <typename FsOut>
inline void FillNearOpticalEmpty180(FsOut* fs) {
  if (!fs) {
    return;
  }
  float surr[kFsEmptyN];
  gf_fs_envelope::SurroundFillEmpty180(surr, gf_fs_envelope::SideLatM());
  for (int i = 0; i < kFsEmptyN; ++i) {
    const float ang = BinAngRad(i);
    float r;
    if (InFrontFov(ang)) {
      r = kFsNearFrontCapM;
    } else if (InRearFov(ang)) {
      r = gf_fs_envelope::RearCapM();
    } else {
      r = (surr[i] >= 0.5f) ? surr[i] : 0.5f;
    }
    fs->d_r_m[i] = r;
    fs->type[i] = static_cast<std::uint8_t>(FsBoundType::Optical);
  }
}

/** Fill FreespaceNear Empty180 from objects (SIL / stub FSD). */
template <typename FsOut>
inline void ComputeFreespaceNear(const ObjSample* objs, int n_obj, std::uint64_t ts_ns,
                                 FsOut* fs) {
  if (!fs) {
    return;
  }
  *fs = {};
  fs->timestamp_ns = ts_ns;
  fs->valid = 1;
  FillNearOpticalEmpty180(fs);

  const float twopi = 6.2831853f;
  const int n = n_obj < 0 ? 0 : n_obj;
  for (int j = 0; j < n; ++j) {
    const float x = objs[j].long_dist_m;
    const float y = objs[j].lat_dist_m;
    const float hl = std::max(0.4f, objs[j].half_l_m);
    const float hw = std::max(0.3f, objs[j].half_w_m);
    for (int i = 0; i < kFsEmptyN; ++i) {
      const float ang = BinAngRad(i);
      const float ca = std::cos(ang);
      const float sa = std::sin(ang);
      float tmin = 0.0f, tmax = 1.0e6f;
      auto slab = [&](float p0, float d, float b0, float b1) {
        if (std::fabs(d) < 1e-6f) {
          if (p0 < b0 || p0 > b1) {
            tmin = 1.0e6f;
          }
          return;
        }
        float t1 = (b0 - p0) / d;
        float t2 = (b1 - p0) / d;
        if (t1 > t2) {
          std::swap(t1, t2);
        }
        tmin = std::max(tmin, t1);
        tmax = std::min(tmax, t2);
      };
      slab(0.0f, ca, x - hl, x + hl);
      slab(0.0f, sa, y - hw, y + hw);
      if (tmin < tmax && tmax > 0.0f) {
        const float t_enter = std::max(0.5f, tmin);
        if (t_enter + 0.05f < fs->d_r_m[i]) {
          fs->d_r_m[i] = t_enter;
          fs->type[i] = static_cast<std::uint8_t>(FsBoundType::Car);
        }
      }
    }
    (void)twopi;
  }
}

/** Optional axis clears derived from Empty180 (not wire fields). */
inline void AxisFromNear180(const float* d_r, float* d_front, float* d_rear, float* d_left,
                            float* d_right) {
  float df = 0.5f, dr = 0.5f, dl = 0.5f, drr = 0.5f;
  if (d_r) {
    for (int i = 0; i < kFsEmptyN; ++i) {
      const float ang = BinAngRad(i);
      const float ca = std::cos(ang);
      const float sa = std::sin(ang);
      const float r = d_r[i];
      if (ca > 0.85f) {
        df = std::max(df, r * ca);
      }
      if (ca < -0.85f) {
        dr = std::max(dr, r * (-ca));
      }
      if (sa > 0.85f) {
        dl = std::max(dl, r * sa);
      }
      if (sa < -0.85f) {
        drr = std::max(drr, r * (-sa));
      }
    }
  }
  if (d_front) {
    *d_front = df;
  }
  if (d_rear) {
    *d_rear = dr;
  }
  if (d_left) {
    *d_left = dl;
  }
  if (d_right) {
    *d_right = drr;
  }
}

}  // namespace gf_surround
