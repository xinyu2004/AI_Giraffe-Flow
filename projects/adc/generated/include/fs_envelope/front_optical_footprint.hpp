#pragma once

// Front camera optical ground: image-rectangle frustum ∩ z=0 ∩ x≤d_empty.
// Shared by planning fuse. Not BEV observer mount.

#include "fs_envelope/fs_envelope_cal.hpp"
#include "fs_envelope/fs_mounts.hpp"

#include <algorithm>
#include <cmath>

namespace gf_fs_envelope {

struct FrontOptics {
  float x_m{0.55f};
  float y_m{0.0f};
  float z_m{1.35f};
  float pitch_deg{-5.0f};
  float yaw_deg{0.0f};
  float roll_deg{0.0f};
  float fov_h_deg{100.0f};
  float image_w{2048.0f};
  float image_h{1536.0f};
};

inline FrontOptics FrontOpticsFromProduct() {
  const CamMount& m = FrontMount();
  FrontOptics o;
  o.x_m = m.x;
  o.y_m = m.y;
  o.z_m = m.z;
  o.pitch_deg = m.pitch_deg;
  o.yaw_deg = m.yaw_deg;
  o.roll_deg = m.roll_deg;
  o.fov_h_deg = m.fov_deg > 1.0f ? m.fov_deg : kFsFrontFovDeg;
  o.image_w = m.w > 1.0f ? m.w : 2048.0f;
  o.image_h = m.h > 1.0f ? m.h : 1536.0f;
  return o;
}

inline float Deg2RadF(float d) { return d * (3.14159265f / 180.0f); }

inline float FrontVfovHalfRad(const FrontOptics& cam) {
  const float hf = 0.5f * Deg2RadF(cam.fov_h_deg);
  const float wh = std::max(cam.image_w, 1.0f) / std::max(cam.image_h, 1.0f);
  return std::atan(std::tan(hf) / wh);
}

/** Build cam axes: +X optical, +Y left, +Z up (world). */
inline void FrontCamAxes(const FrontOptics& cam, float* fx, float* fy, float* fz, float* lx,
                         float* ly, float* lz, float* ux, float* uy, float* uz) {
  const float yaw = Deg2RadF(cam.yaw_deg);
  const float pitch = Deg2RadF(cam.pitch_deg);
  const float cp = std::cos(pitch);
  const float sp = std::sin(pitch);
  const float cy = std::cos(yaw);
  const float sy = std::sin(yaw);
  *fx = cp * cy;
  *fy = cp * sy;
  *fz = sp;
  *lx = -(*fy);
  *ly = *fx;
  *lz = 0.0f;
  const float ln = std::sqrt((*lx) * (*lx) + (*ly) * (*ly));
  if (ln < 1.0e-6f) {
    *lx = 0.0f;
    *ly = 1.0f;
  } else {
    *lx /= ln;
    *ly /= ln;
  }
  *ux = (*fy) * (*lz) - (*fz) * (*ly);
  *uy = (*fz) * (*lx) - (*fx) * (*lz);
  *uz = (*fx) * (*ly) - (*fy) * (*lx);
  const float un = std::sqrt((*ux) * (*ux) + (*uy) * (*uy) + (*uz) * (*uz));
  if (un > 1.0e-6f) {
    *ux /= un;
    *uy /= un;
    *uz /= un;
  }
  const float roll = Deg2RadF(cam.roll_deg);
  if (std::fabs(roll) > 1.0e-6f) {
    const float cr = std::cos(roll);
    const float sr = std::sin(roll);
    const float lx2 = cr * (*lx) + sr * (*ux);
    const float ly2 = cr * (*ly) + sr * (*uy);
    const float lz2 = cr * (*lz) + sr * (*uz);
    const float ux2 = -sr * (*lx) + cr * (*ux);
    const float uy2 = -sr * (*ly) + cr * (*uy);
    const float uz2 = -sr * (*lz) + cr * (*uz);
    *lx = lx2;
    *ly = ly2;
    *lz = lz2;
    *ux = ux2;
    *uy = uy2;
    *uz = uz2;
  }
}

/** Image-rectangle test: |cy/cx|≤tan(hfov/2) ∧ |cz/cx|≤tan(vfov/2). */
inline bool PointInFrontFrustum(float px, float py, const FrontOptics& cam) {
  float fx, fy, fz, lx, ly, lz, ux, uy, uz;
  FrontCamAxes(cam, &fx, &fy, &fz, &lx, &ly, &lz, &ux, &uy, &uz);
  const float vx = px - cam.x_m;
  const float vy = py - cam.y_m;
  const float vz = 0.0f - cam.z_m;
  const float cx = vx * fx + vy * fy + vz * fz;
  const float cy_c = vx * lx + vy * ly + vz * lz;
  const float cz = vx * ux + vy * uy + vz * uz;
  if (cx <= 1.0e-3f) {
    return false;
  }
  const float hf = 0.5f * Deg2RadF(cam.fov_h_deg);
  const float vf = FrontVfovHalfRad(cam);
  const float th = std::tan(hf);
  const float tv = std::tan(vf);
  return std::fabs(cy_c / cx) <= th + 1.0e-4f && std::fabs(cz / cx) <= tv + 1.0e-4f;
}

/**
 * Along ego bearing θ: max range still in front image rectangle ∩ x≤d_empty.
 * <0 if this bearing never hits the optical ground footprint.
 */
inline float FrontEmptyR(float th, float d_empty, const FrontOptics& cam, float eps = 1.0e-3f) {
  const float c = std::cos(th);
  const float s = std::sin(th);
  if (c < 0.05f) {
    return -1.0f;
  }
  const float d_cap = std::max(0.5f, std::min(kFsFrontFarCapM, d_empty));
  float t_hi = d_cap / std::max(c, eps);
  t_hi = std::min(t_hi, 250.0f);
  if (t_hi < 0.5f) {
    return -1.0f;
  }
  float best = -1.0f;
  constexpr int kSamp = 64;
  for (int i = 0; i < kSamp; ++i) {
    const float uu = static_cast<float>(i) / static_cast<float>(kSamp - 1);
    const float t = 0.5f + (t_hi - 0.5f) * uu;
    const float x = t * c;
    const float y = t * s;
    if (x > d_cap + 0.05f) {
      break;
    }
    if (PointInFrontFrustum(x, y, cam)) {
      best = t;
    }
  }
  if (best < 0.5f) {
    return -1.0f;
  }
  float lo = std::max(0.5f, best - (t_hi - 0.5f) / static_cast<float>(kSamp));
  float hi = std::min(t_hi, best + (t_hi - 0.5f) / static_cast<float>(kSamp) * 2.0f);
  for (int it = 0; it < 14; ++it) {
    const float mid = 0.5f * (lo + hi);
    const float x = mid * c;
    const float y = mid * s;
    if (x <= d_cap + 0.05f && PointInFrontFrustum(x, y, cam)) {
      lo = mid;
    } else {
      hi = mid;
    }
  }
  return lo;
}

/** Along any ego bearing θ: max range in camera image rectangle ∩ r≤r_cap. <0 if none. */
inline float OpticalEmptyR(float th, float r_cap, const FrontOptics& cam, float eps = 1.0e-3f) {
  const float c = std::cos(th);
  const float s = std::sin(th);
  const float d_cap = std::max(0.5f, r_cap);
  float t_hi = std::min(d_cap, 80.0f);
  if (t_hi < 0.5f) {
    return -1.0f;
  }
  float best = -1.0f;
  constexpr int kSamp = 64;
  for (int i = 0; i < kSamp; ++i) {
    const float uu = static_cast<float>(i) / static_cast<float>(kSamp - 1);
    const float t = 0.5f + (t_hi - 0.5f) * uu;
    if (PointInFrontFrustum(t * c, t * s, cam)) {
      best = t;
    }
  }
  if (best < 0.5f) {
    return -1.0f;
  }
  float lo = std::max(0.5f, best - (t_hi - 0.5f) / static_cast<float>(kSamp));
  float hi = std::min(t_hi, best + (t_hi - 0.5f) / static_cast<float>(kSamp) * 2.0f);
  for (int it = 0; it < 12; ++it) {
    const float mid = 0.5f * (lo + hi);
    if (PointInFrontFrustum(mid * c, mid * s, cam)) {
      lo = mid;
    } else {
      hi = mid;
    }
  }
  (void)eps;
  return lo;
}

/** ADC 4-cam surround (compose-frozen stubs ≡ req.yaml): mirrors + bumpers. */
inline FrontOptics SurroundOpticsFl() {
  // Left rear-view mirror, looking left.
  return {1.05f, 1.05f, 1.05f, -12.0f, 90.0f, 0.0f, 90.0f, 1280.0f, 800.0f};
}
inline FrontOptics SurroundOpticsFr() {
  // Right rear-view mirror, looking right.
  return {1.05f, -1.05f, 1.05f, -12.0f, -90.0f, 0.0f, 90.0f, 1280.0f, 800.0f};
}
inline FrontOptics SurroundOpticsFrontBumper() {
  return {0.55f, 0.0f, 1.35f, -5.0f, 0.0f, 0.0f, 100.0f, 2048.0f, 1536.0f};
}
inline FrontOptics SurroundOpticsRearBumper() {
  return {-0.85f, 0.0f, 1.15f, -8.0f, 180.0f, 0.0f, 120.0f, 1920.0f, 1080.0f};
}

/**
 * Rasterize one camera's image-rectangle rays onto z=0, write ego-polar Empty180 bins.
 * Rays are cast from the camera optical center (not ego origin).
 */
inline void SurroundRasterizeCamToBins(const FrontOptics& cam, float side_cap, float* r_bins) {
  if (!r_bins || cam.z_m < 0.05f) {
    return;
  }
  float fx, fy, fz, lx, ly, lz, ux, uy, uz;
  FrontCamAxes(cam, &fx, &fy, &fz, &lx, &ly, &lz, &ux, &uy, &uz);
  const float hf = 0.5f * Deg2RadF(cam.fov_h_deg);
  const float vf = FrontVfovHalfRad(cam);
  const float cap = std::max(0.5f, side_cap);
  constexpr float twopi = 6.2831853f;
  // Dense azimuth; bias elevation toward ground (lower image).
  constexpr int kAz = 72;
  constexpr int kEl = 48;
  for (int ia = 0; ia < kAz; ++ia) {
    const float az = -hf + (2.0f * hf) * ((static_cast<float>(ia) + 0.5f) / static_cast<float>(kAz));
    const float taz = std::tan(az);
    for (int ie = 0; ie < kEl; ++ie) {
      const float el = -vf + (2.0f * vf) * ((static_cast<float>(ie) + 0.5f) / static_cast<float>(kEl));
      const float tel = std::tan(el);
      // Camera frame: +X optical, +Y left, +Z up.
      float wx = fx + taz * lx + tel * ux;
      float wy = fy + taz * ly + tel * uy;
      float wz = fz + taz * lz + tel * uz;
      const float wn = std::sqrt(wx * wx + wy * wy + wz * wz);
      if (wn < 1.0e-6f) {
        continue;
      }
      wx /= wn;
      wy /= wn;
      wz /= wn;
      if (wz >= -1.0e-4f) {
        continue;  // parallel to ground or sky
      }
      const float t = -cam.z_m / wz;
      if (t < 0.05f || t > 120.0f) {
        continue;
      }
      const float x = cam.x_m + t * wx;
      const float y = cam.y_m + t * wy;
      float r = std::sqrt(x * x + y * y);
      if (r < 0.5f) {
        continue;
      }
      if (r > cap) {
        r = cap;
      }
      float a = std::atan2(y, x);
      if (a < 0.0f) {
        a += twopi;
      }
      int s = static_cast<int>(a / twopi * static_cast<float>(kFsEmptyN)) % kFsEmptyN;
      if (s < 0) {
        s += kFsEmptyN;
      }
      if (r > r_bins[s]) {
        r_bins[s] = r;
      }
    }
  }
}

/** Fill surround Empty180: L/R mirrors + front/rear bumpers ∩ side_cap. */
inline void SurroundFillEmpty180(float* r_bins, float side_cap) {
  if (!r_bins) {
    return;
  }
  for (int i = 0; i < kFsEmptyN; ++i) {
    r_bins[i] = -1.0f;
  }
  const FrontOptics cams[4] = {SurroundOpticsFl(), SurroundOpticsFr(), SurroundOpticsFrontBumper(),
                               SurroundOpticsRearBumper()};
  for (const FrontOptics& cam : cams) {
    SurroundRasterizeCamToBins(cam, side_cap, r_bins);
  }
}

/**
 * Side empty at ego bearing θ: from cached cam→ground→bin fill (not ego-ray PointInFrustum).
 * <0 if no surround camera sees ground along that bin.
 */
inline float SurroundSideEmptyR(float th, float side_cap) {
  const float cap = std::max(0.5f, side_cap);
  thread_local float cache_r[kFsEmptyN];
  thread_local float cache_cap = -1.0f;
  thread_local bool cache_ok = false;
  if (!cache_ok || std::fabs(cache_cap - cap) > 1.0e-3f) {
    SurroundFillEmpty180(cache_r, cap);
    cache_cap = cap;
    cache_ok = true;
  }
  constexpr float twopi = 6.2831853f;
  float a = th;
  while (a < 0.0f) {
    a += twopi;
  }
  while (a >= twopi) {
    a -= twopi;
  }
  int s = static_cast<int>(a / twopi * static_cast<float>(kFsEmptyN)) % kFsEmptyN;
  if (s < 0) {
    s += kFsEmptyN;
  }
  return (cache_r[s] >= 0.5f) ? cache_r[s] : -1.0f;
}


}  // namespace gf_fs_envelope
