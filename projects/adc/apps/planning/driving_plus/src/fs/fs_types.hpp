#pragma once

// Ground-domain FS value types. Stages pass const in → new out (no shared mutable d_occ).

#include "fs_envelope/fs_envelope_cal.hpp"
#include "fs_envelope/front_optical_footprint.hpp"

#include <cstdint>

namespace gf_plan_fs {

using gf_fs_envelope::kFsFrontFarCapM;
using gf_fs_envelope::kFsNearFrontCapM;
using gf_fs_envelope::kFsEmptyN;

/** Pack = one vertex per Empty180 bin (no downsample). */
inline constexpr int kFsPolyMax = kFsEmptyN;

/** Optical FS region — scoped at BuildOpticalEmpty(region). */
enum class FsRegion : std::uint8_t { Front = 0, Surround = 1, Rear = 2 };
/** Alias: Side == Surround (周视). */
inline constexpr FsRegion FsRegionSide = FsRegion::Surround;

/** Ego-frame cubic road edge y = c0 + c1 x + c2 x² + c3 x³. */
struct RoadEdgePoly {
  bool valid{false};
  bool hard{false};
  float c0{0.0f};
  float c1{0.0f};
  float c2{0.0f};
  float c3{0.0f};
  float vr_m{120.0f};
};

inline float RoadEdgeY(const RoadEdgePoly& e, float x) {
  return e.c0 + e.c1 * x + e.c2 * x * x + e.c3 * x * x * x;
}

/** LRE/LH cubics trusted on [0, VR_End]. Behind ego: linear c0+c1·x (do not collapse to x=0). */
inline float RoadQueryX(const RoadEdgePoly& e, float x) {
  float xq = x;
  if (xq < 0.0f) {
    return xq;
  }
  if (e.vr_m > 0.5f && xq > e.vr_m) {
    xq = e.vr_m;
  }
  return xq;
}

inline float RoadEdgeYFwd(const RoadEdgePoly& e, float x) {
  if (x < 0.0f) {
    return e.c0 + e.c1 * x;
  }
  return RoadEdgeY(e, RoadQueryX(e, x));
}

/** Closed contour for wire + BEV (Empty180 Pack). */
struct GroundPoly {
  int n{0};
  float x[kFsPolyMax]{};
  float y[kFsPolyMax]{};
  bool valid{false};
};

struct FsOccSample {
  float x_m{0.0f};
  float y_m{0.0f};
  float half_w_m{0.9f};
  float half_l_m{2.0f};
  bool hard_world{false};
};

/** ME/FCM static classes that must carve all bearings (cone/barrier/barrel). */
inline bool IsHardStaticCls(std::uint8_t cls) {
  // Common ME: 9=cone, 10=barrel, 11=barrier-ish — keep permissive for SIL stubs.
  return cls == 9 || cls == 10 || cls == 11 || cls == 12;
}

/** Product camera mount (camera_contract). */
struct CamOptics {
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

using FrontCamMount = CamOptics;

inline gf_fs_envelope::FrontOptics ToOptics(const CamOptics& cam) {
  gf_fs_envelope::FrontOptics o;
  o.x_m = cam.x_m;
  o.y_m = cam.y_m;
  o.z_m = cam.z_m;
  o.pitch_deg = cam.pitch_deg;
  o.yaw_deg = cam.yaw_deg;
  o.roll_deg = cam.roll_deg;
  o.fov_h_deg = cam.fov_h_deg;
  o.image_w = cam.image_w;
  o.image_h = cam.image_h;
  return o;
}

inline CamOptics DefaultFrontCam() {
  const gf_fs_envelope::FrontOptics o = gf_fs_envelope::FrontOpticsFromProduct();
  CamOptics c;
  c.x_m = o.x_m;
  c.y_m = o.y_m;
  c.z_m = o.z_m;
  c.pitch_deg = o.pitch_deg;
  c.yaw_deg = o.yaw_deg;
  c.roll_deg = o.roll_deg;
  c.fov_h_deg = o.fov_h_deg;
  c.image_w = o.image_w;
  c.image_h = o.image_h;
  return c;
}

/** ADC camera_contract stubs (compose-frozen defaults). */
inline CamOptics DefaultFlCam() {
  return {1.05f, 1.05f, 1.05f, -12.0f, 90.0f, 0.0f, 90.0f, 1280.0f, 800.0f};
}
inline CamOptics DefaultFrCam() {
  return {1.05f, -1.05f, 1.05f, -12.0f, -90.0f, 0.0f, 90.0f, 1280.0f, 800.0f};
}
inline CamOptics DefaultRlCam() {
  return {-0.6f, 1.0f, 1.0f, -15.0f, 135.0f, 0.0f, 90.0f, 1280.0f, 800.0f};
}
inline CamOptics DefaultRrCam() {
  return {-0.6f, -1.0f, 1.0f, -15.0f, -135.0f, 0.0f, 90.0f, 1280.0f, 800.0f};
}
inline CamOptics DefaultRearCam() {
  return {-0.85f, 0.0f, 1.15f, -8.0f, 180.0f, 0.0f, 120.0f, 1920.0f, 1080.0f};
}

inline bool PointInCamFrustum(float px, float py, const CamOptics& cam) {
  return gf_fs_envelope::PointInFrontFrustum(px, py, ToOptics(cam));
}

}  // namespace gf_plan_fs
