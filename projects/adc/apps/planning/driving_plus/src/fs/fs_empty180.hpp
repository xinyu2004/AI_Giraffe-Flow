#pragma once

// Empty180 stack: L0 baseline → L1 lane → L2 occ (restore+apply) → L3 pack → L4 D_see.
// Single representation: r[180]+type[180]. Compose orchestrates; layers do not call each other.

#include "fs/fs_types.hpp"
#include "fs/fs_lane_clear.hpp"
#include "fs_envelope/fs_envelope_cal.hpp"
#include "fs_envelope/fs_mounts.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>

namespace gf_plan_fs {

using gf_fs_envelope::kFsEmptyN;

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

struct FsEmpty180 {
  float r[kFsEmptyN]{};
  std::uint8_t type[kFsEmptyN]{};
  bool valid{false};
};

inline float FsBinAngRad(int i) {
  const float twopi = 6.2831853f;
  return (static_cast<float>(i) + 0.5f) * (twopi / static_cast<float>(kFsEmptyN));
}

inline void FsWrapPi(float* a) {
  constexpr float pi = 3.14159265f;
  constexpr float twopi = 6.2831853f;
  while (*a > pi) {
    *a -= twopi;
  }
  while (*a < -pi) {
    *a += twopi;
  }
}

inline bool FsInFrontFov(float ang) {
  constexpr float pi = 3.14159265f;
  const float half = 0.5f * gf_fs_envelope::FrontFovDeg() * (pi / 180.0f);
  float a = ang;
  FsWrapPi(&a);
  return std::fabs(a) <= half;
}

inline bool FsInRearFov(float ang) {
  constexpr float pi = 3.14159265f;
  const float half = 0.5f * gf_fs_envelope::RearFovDeg() * (pi / 180.0f);
  float a = ang - pi;
  FsWrapPi(&a);
  return std::fabs(a) <= half;
}

inline std::uint32_t FsHashMix(std::uint32_t h, std::uint32_t v) {
  h ^= v + 0x9e3779b9u + (h << 6) + (h >> 2);
  return h;
}

/** Fingerprint helpers for dirty layers. */
inline std::uint32_t FsFpNear180(const float* r, const std::uint8_t* ty, int n) {
  std::uint32_t h = 0;
  if (!r) {
    return h;
  }
  for (int i = 0; i < n; ++i) {
    h = FsHashMix(h, static_cast<std::uint32_t>(std::lround(r[i] * 2.0f) + 100000));
    if (ty) {
      h = FsHashMix(h, ty[i]);
    }
  }
  return h;
}

/** Fingerprint one cubic edge (valid + hard + c0..c3 + VR). Curve must dirty Restrict. */
inline std::uint32_t FsFpOneRoad(const RoadEdgePoly& e, std::uint32_t tag) {
  std::uint32_t h = tag;
  if (!e.valid) {
    return h;
  }
  h = FsHashMix(h, e.hard ? 1u : 2u);
  // Quantize fine enough that bend (c1–c3) invalidates cache; c0 alone was too coarse.
  h = FsHashMix(h, static_cast<std::uint32_t>(std::lround(e.c0 * 100.0f) + 500000));
  h = FsHashMix(h, static_cast<std::uint32_t>(std::lround(e.c1 * 1000.0f) + 500000));
  h = FsHashMix(h, static_cast<std::uint32_t>(std::lround(e.c2 * 1.0e4f) + 500000));
  h = FsHashMix(h, static_cast<std::uint32_t>(std::lround(e.c3 * 1.0e5f) + 500000));
  h = FsHashMix(h, static_cast<std::uint32_t>(std::lround(e.vr_m * 2.0f) + 1000));
  return h;
}

inline std::uint32_t FsFpRoad(const RoadEdgePoly& L, const RoadEdgePoly& R) {
  return FsHashMix(FsFpOneRoad(L, 1u), FsFpOneRoad(R, 2u));
}

inline std::uint32_t FsFpOcc(const FsOccSample* objs, int n_obj) {
  std::uint32_t h = static_cast<std::uint32_t>(n_obj);
  if (!objs) {
    return h;
  }
  for (int i = 0; i < n_obj; ++i) {
    h = FsHashMix(h, static_cast<std::uint32_t>(std::lround(objs[i].x_m * 2.0f) + 50000));
    h = FsHashMix(h, static_cast<std::uint32_t>(std::lround(objs[i].y_m * 2.0f) + 50000));
  }
  return h;
}

// ---- L0: optical / FSD baseline (no occ, no lane) ----
// Front = camera cone ∩ ground ∩ x≤cap (FrontEmptyR). Not r=cap on every FOV bin.
// Front corners also eat the surround side wall (|y|≤SideLatM). LRE (L1) only tightens.

inline float FsFrontLatWallR(float ang, float side_lat_m) {
  const float sa = std::fabs(std::sin(ang));
  if (sa < 1.0e-3f) {
    return 1.0e6f;
  }
  return std::max(0.5f, side_lat_m / sa);
}

inline void FsBaselineFromOpticsFsd(FsEmpty180* out, const float* near_r, const std::uint8_t* near_ty,
                                    int near_n, float front_cap_m) {
  if (!out) {
    return;
  }
  *out = {};
  const float fcap = std::max(0.5f, std::min(kFsFrontFarCapM, front_cap_m));
  const float y_side = gf_fs_envelope::SideLatM();
  const gf_fs_envelope::FrontOptics cam = gf_fs_envelope::FrontOpticsFromProduct();
  float surr[kFsEmptyN];
  gf_fs_envelope::SurroundFillEmpty180(surr, y_side);
  for (int i = 0; i < kFsEmptyN; ++i) {
    const float ang = FsBinAngRad(i);
    float r;
    if (FsInFrontFov(ang)) {
      r = gf_fs_envelope::FrontEmptyR(ang, fcap, cam);
      if (r < 0.5f) {
        r = (surr[i] >= 0.5f) ? surr[i] : 0.5f;
      }
      r = std::min(r, FsFrontLatWallR(ang, y_side));
    } else if (FsInRearFov(ang)) {
      r = gf_fs_envelope::RearCapM();
    } else {
      r = (surr[i] >= 0.5f) ? surr[i] : 0.5f;
    }
    std::uint8_t ty = static_cast<std::uint8_t>(FsBoundType::Optical);
    // Near empty optical floor must not cover driving front far empty (15 ≠ 120).
    // Front FOV: only real Near bites (non-Optical). Side/rear: Near is surround author.
    if (near_r && near_n == kFsEmptyN) {
      const float nr = near_r[i];
      const std::uint8_t nty =
          near_ty ? near_ty[i] : static_cast<std::uint8_t>(FsBoundType::Unknown);
      const bool front = FsInFrontFov(ang);
      const bool near_empty_opt = (nty == static_cast<std::uint8_t>(FsBoundType::Optical));
      if (nr > 0.5f && nr + 0.05f < r) {
        if (front && near_empty_opt) {
          // keep driving optical r
        } else {
          r = nr;
          ty = nty;
        }
      }
    }
    if (FsInFrontFov(ang)) {
      r = std::min(r, FsFrontLatWallR(ang, y_side));
    }
    out->r[i] = std::max(0.5f, r);
    out->type[i] = ty;
  }
  out->valid = true;
}

// ---- L1: lane / road shorten → baseline ----

inline bool FsPointInLaneCorridor(float x, float y, const RoadEdgePoly& road_left,
                                  const RoadEdgePoly& road_right, const RoadEdgePoly* hard_walls,
                                  int n_hard) {
  const bool have_L = road_left.valid;
  const bool have_R = road_right.valid;
  constexpr float kRoadEpsM = 1.0e-3f;
  if (!(have_L || have_R || (hard_walls && n_hard > 0))) {
    return true;
  }
  if (have_L && have_R) {
    float yl = RoadEdgeYFwd(road_left, x);
    float yr = RoadEdgeYFwd(road_right, x);
    if (yr > yl) {
      std::swap(yl, yr);
    }
    if (y > yl + kRoadEpsM || y < yr - kRoadEpsM) {
      return false;
    }
  } else if (have_L) {
    if (y > RoadEdgeYFwd(road_left, x) + kRoadEpsM) {
      return false;
    }
  } else if (have_R) {
    if (y < RoadEdgeYFwd(road_right, x) - kRoadEpsM) {
      return false;
    }
  }
  if (hard_walls) {
    for (int h = 0; h < n_hard; ++h) {
      if (!hard_walls[h].valid || !hard_walls[h].hard) {
        continue;
      }
      const float yw = RoadEdgeYFwd(hard_walls[h], x);
      if (hard_walls[h].c0 > 0.0f && y > yw + kRoadEpsM) {
        return false;
      }
      if (hard_walls[h].c0 < 0.0f && y < yw - kRoadEpsM) {
        return false;
      }
    }
  }
  return true;
}

inline bool FsChordInLaneCorridor(float x0, float y0, float x1, float y1,
                                  const RoadEdgePoly& road_left, const RoadEdgePoly& road_right,
                                  const RoadEdgePoly* hard_walls, int n_hard, int samples = 8) {
  for (int k = 0; k <= samples; ++k) {
    const float t = static_cast<float>(k) / static_cast<float>(samples);
    const float x = x0 + t * (x1 - x0);
    const float y = y0 + t * (y1 - y0);
    if (!FsPointInLaneCorridor(x, y, road_left, road_right, hard_walls, n_hard)) {
      return false;
    }
  }
  return true;
}

inline void FsRestrictLane180(FsEmpty180* io, const RoadEdgePoly& road_left,
                              const RoadEdgePoly& road_right, const RoadEdgePoly* hard_walls,
                              int n_hard) {
  if (!io || !io->valid) {
    return;
  }
  const bool have_L = road_left.valid;
  const bool have_R = road_right.valid;
  const bool have_hard = hard_walls && n_hard > 0;
  // One-sided LRE/LH still clips that side; both → corridor.
  // Full ring: behind ego uses RoadEdgeYFwd linear (c0+c1·x), same as BEV PolyYAt.
  if (!(have_L || have_R || have_hard)) {
    return;
  }
  for (int i = 0; i < kFsEmptyN; ++i) {
    const float ang = FsBinAngRad(i);
    const float ca = std::cos(ang);
    const float sa = std::sin(ang);
    const float r_max = io->r[i];
    float r_ok = 0.5f;
    if (FsPointInLaneCorridor(r_max * ca, r_max * sa, road_left, road_right, hard_walls, n_hard)) {
      r_ok = r_max;
    } else {
      float lo = 0.5f;
      float hi = r_max;
      for (int it = 0; it < 18; ++it) {
        const float mid = 0.5f * (lo + hi);
        if (FsPointInLaneCorridor(mid * ca, mid * sa, road_left, road_right, hard_walls, n_hard)) {
          lo = mid;
        } else {
          hi = mid;
        }
      }
      r_ok = lo;
    }
    if (r_ok + 0.05f < io->r[i]) {
      io->r[i] = std::max(0.5f, r_ok);
      io->type[i] = static_cast<std::uint8_t>(FsBoundType::LaneBound);
    }
  }
  // No lane_clear.host on contour (flattens front / kills rabbit ears).
}

/**
 * Kill rabbit ears on forward LRE: vertices may be in-corridor while the Empty180 rim
 * chord cuts outside a curve. Pull the *longer* ray in toward the shorter neighbor.
 *
 * Scope: forward(+x) only. Do not dig rear/side or collapse to dig-floor.
 */
inline void FsClipEmpty180ChordsToLane(FsEmpty180* io, const RoadEdgePoly& road_left,
                                       const RoadEdgePoly& road_right,
                                       const RoadEdgePoly* hard_walls, int n_hard) {
  if (!io || !io->valid) {
    return;
  }
  if (!(road_left.valid || road_right.valid || (hard_walls && n_hard > 0))) {
    return;
  }
  constexpr float kDigM = 0.75f;
  constexpr float kMinCosFwd = 0.05f;
  for (int pass = 0; pass < 3; ++pass) {
    bool any = false;
    for (int i = 0; i < kFsEmptyN; ++i) {
      const int j = (i + 1) % kFsEmptyN;
      float ri = io->r[i];
      float rj = io->r[j];
      if (ri < kDigM || rj < kDigM) {
        continue;
      }
      const float ai = FsBinAngRad(i);
      const float aj = FsBinAngRad(j);
      if (FsInRearFov(ai) || FsInRearFov(aj)) {
        continue;
      }
      const float cai = std::cos(ai);
      const float sai = std::sin(ai);
      const float caj = std::cos(aj);
      const float saj = std::sin(aj);
      if (cai < kMinCosFwd || caj < kMinCosFwd) {
        continue;
      }
      auto chord_ok = [&](float ra, float rb) {
        return FsChordInLaneCorridor(ra * cai, ra * sai, rb * caj, rb * saj, road_left, road_right,
                                     hard_walls, n_hard, 10);
      };
      if (chord_ok(ri, rj)) {
        continue;
      }
      // Pull longer ray down toward shorter (floor ≈ 0.85× shorter). Never dig the short end.
      auto shrink_long = [&](float& r_long, float r_short, bool long_is_i) {
        const float floor_r = std::max(kDigM, 0.85f * r_short);
        if (r_long <= floor_r + 0.05f) {
          return;
        }
        float lo = floor_r;
        float hi = r_long;
        for (int it = 0; it < 14; ++it) {
          const float mid = 0.5f * (lo + hi);
          const bool ok = long_is_i ? chord_ok(mid, r_short) : chord_ok(r_short, mid);
          if (ok) {
            lo = mid;
          } else {
            hi = mid;
          }
        }
        const bool ok = long_is_i ? chord_ok(lo, r_short) : chord_ok(r_short, lo);
        if (ok && lo + 0.05f < r_long) {
          r_long = lo;
          any = true;
        }
      };
      if (ri >= rj) {
        shrink_long(ri, rj, true);
        io->r[i] = ri;
      } else {
        shrink_long(rj, ri, false);
        io->r[j] = rj;
      }
      if (any) {
        if (io->type[i] == static_cast<std::uint8_t>(FsBoundType::Optical) ||
            io->type[i] == static_cast<std::uint8_t>(FsBoundType::Unknown)) {
          io->type[i] = static_cast<std::uint8_t>(FsBoundType::LaneBound);
        }
        if (io->type[j] == static_cast<std::uint8_t>(FsBoundType::Optical) ||
            io->type[j] == static_cast<std::uint8_t>(FsBoundType::Unknown)) {
          io->type[j] = static_cast<std::uint8_t>(FsBoundType::LaneBound);
        }
      }
    }
    if (!any) {
      break;
    }
  }
}

// ---- L2: occ restore + apply (never mutates baseline) ----

inline int FsBinOfXY(float x, float y) {
  const float twopi = 6.2831853f;
  float a = std::atan2(y, x);
  if (a < 0.0f) {
    a += twopi;
  }
  int s = static_cast<int>(a / twopi * static_cast<float>(kFsEmptyN)) % kFsEmptyN;
  if (s < 0) {
    s += kFsEmptyN;
  }
  return s;
}

inline void FsOccRestoreBins(FsEmpty180* active, const FsEmpty180& baseline,
                             const bool* dirty_bins) {
  if (!active || !baseline.valid) {
    return;
  }
  for (int i = 0; i < kFsEmptyN; ++i) {
    if (!dirty_bins || dirty_bins[i]) {
      active->r[i] = baseline.r[i];
      active->type[i] = baseline.type[i];
    }
  }
  active->valid = baseline.valid;
}

inline void FsOccApply180(FsEmpty180* active, const FsOccSample* objs, int n_obj,
                          bool* hit_bins_out) {
  if (!active || !active->valid || !objs || n_obj <= 0) {
    return;
  }
  for (int j = 0; j < n_obj; ++j) {
    const FsOccSample& o = objs[j];
    const float hl = std::max(0.4f, o.half_l_m);
    const float hw = std::max(0.3f, o.half_w_m);
    for (int i = 0; i < kFsEmptyN; ++i) {
      const float ang = FsBinAngRad(i);
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
      slab(0.0f, ca, o.x_m - hl, o.x_m + hl);
      slab(0.0f, sa, o.y_m - hw, o.y_m + hw);
      if (tmin < tmax && tmax > 0.0f) {
        const float t_enter = std::max(0.5f, tmin);
        if (t_enter + 0.05f < active->r[i]) {
          active->r[i] = t_enter;
          active->type[i] = static_cast<std::uint8_t>(FsBoundType::Car);
          if (hit_bins_out) {
            hit_bins_out[i] = true;
          }
        }
      }
    }
  }
}

// ---- L3: pack poly ----

inline GroundPoly FsPack180ToPoly(const FsEmpty180& active) {
  GroundPoly p;
  if (!active.valid) {
    return p;
  }
  constexpr float kDigFloorM = 0.5f;
  for (int i = 0; i < kFsEmptyN; ++i) {
    if (p.n >= kFsPolyMax) {
      break;
    }
    const float ang = FsBinAngRad(i);
    const float r = std::max(kDigFloorM, active.r[i]);
    p.x[p.n] = r * std::cos(ang);
    p.y[p.n] = r * std::sin(ang);
    ++p.n;
  }
  p.valid = p.n == kFsEmptyN;
  return p;
}

// Packed contour is star-shaped from ego. Used by path clip + LC land (C preprocess).
inline int FsBinFromXY(float x, float y) {
  constexpr float twopi = 6.2831853f;
  float a = std::atan2(y, x);
  if (a < 0.0f) {
    a += twopi;
  }
  int s = static_cast<int>(a / twopi * static_cast<float>(kFsEmptyN)) % kFsEmptyN;
  if (s < 0) {
    s += kFsEmptyN;
  }
  return s;
}

inline bool FsPointInPacked(float x, float y, const float* px, const float* py, int n,
                            float slack_m = 0.35f) {
  if (!px || !py || n < 8) {
    return false;
  }
  const float r = std::hypot(x, y);
  if (r < 0.5f) {
    return true;
  }
  const int i = std::min(n - 1, FsBinFromXY(x, y));
  const float rb = std::hypot(px[i], py[i]);
  return r <= rb + slack_m;
}

/** Trim traj at the first point that leaves the packed FS. Keeps ≥2 points when possible. */
inline void ClipPathToFreespace(float* xs, float* ys, int* n, const float* px, const float* py,
                                int np) {
  if (!xs || !ys || !n || *n < 2 || !px || !py || np < 8) {
    return;
  }
  const int n0 = *n;
  int keep = 1;
  for (int i = 1; i < n0; ++i) {
    if (FsPointInPacked(xs[i], ys[i], px, py, np)) {
      keep = i + 1;
      continue;
    }
    float lo = 0.0f;
    float hi = 1.0f;
    const float x0 = xs[i - 1];
    const float y0 = ys[i - 1];
    const float x1 = xs[i];
    const float y1 = ys[i];
    for (int it = 0; it < 12; ++it) {
      const float mid = 0.5f * (lo + hi);
      const float xm = x0 + mid * (x1 - x0);
      const float ym = y0 + mid * (y1 - y0);
      if (FsPointInPacked(xm, ym, px, py, np, 0.05f)) {
        lo = mid;
      } else {
        hi = mid;
      }
    }
    xs[i] = x0 + lo * (x1 - x0);
    ys[i] = y0 + lo * (y1 - y0);
    keep = i + 1;
    break;
  }
  if (keep < 2) {
    keep = 2;
  }
  *n = keep;
}

/** Land: target-lane samples must sit in the current FS. Enter and pre-reg hold share this. */
inline bool FsLandInFreespace(int side, const float* px, const float* py, int np, float lane_w_m) {
  if (side == 0) {
    return true;
  }
  if (!px || !py || np < 16) {
    return false;
  }
  const float w = (side > 0 ? 1.0f : -1.0f) * std::max(2.5f, std::min(lane_w_m, 4.5f));
  const float xs[4] = {5.0f, 10.0f, 16.0f, 24.0f};
  int ok = 0;
  for (float x : xs) {
    if (FsPointInPacked(x, 0.55f * w, px, py, np) || FsPointInPacked(x, w, px, py, np)) {
      ++ok;
    }
  }
  return ok >= 3;
}

// ---- L4: short-lived D_see components from active ----

inline float FsDfsFwdFromActive(const FsEmpty180& active) {
  float d = 0.5f;
  if (!active.valid) {
    return d;
  }
  for (int i = 0; i < kFsEmptyN; ++i) {
    const float ang = FsBinAngRad(i);
    const float ca = std::cos(ang);
    if (ca > 0.85f) {
      d = std::max(d, active.r[i] * ca);
    }
  }
  return d;
}

inline float FsAxisClear(const FsEmpty180& active, float ca_min, float ca_max, bool want_neg) {
  float d = 0.5f;
  if (!active.valid) {
    return d;
  }
  for (int i = 0; i < kFsEmptyN; ++i) {
    const float ang = FsBinAngRad(i);
    const float ca = std::cos(ang);
    const float sa = std::sin(ang);
    if (want_neg) {
      if (ca < ca_min) {
        d = std::max(d, active.r[i] * (-ca));
      }
    } else if (ca > ca_max) {
      d = std::max(d, active.r[i] * ca);
    }
    (void)sa;
  }
  return d;
}

inline float FsLatClear(const FsEmpty180& active, bool left) {
  float d = 0.5f;
  if (!active.valid) {
    return d;
  }
  for (int i = 0; i < kFsEmptyN; ++i) {
    const float ang = FsBinAngRad(i);
    const float sa = std::sin(ang);
    if (left && sa > 0.85f) {
      d = std::max(d, active.r[i] * sa);
    }
    if (!left && sa < -0.85f) {
      d = std::max(d, active.r[i] * (-sa));
    }
  }
  return d;
}

struct FsComposeCache {
  FsEmpty180 baseline{};
  FsEmpty180 active{};
  bool hit_bins[kFsEmptyN]{};
  std::uint32_t fp_base{0};
  std::uint32_t fp_occ{0};
  bool have{false};
  GroundPoly poly{};
};

/**
 * Orch: dirty-aware Empty180 compose. Writes poly + optional lane_fwd into FsOut.
 */
template <typename NearFs, typename FsOut>
inline void FsComposeEmpty180(float d_empty_cap_m, const NearFs* near, const FsOccSample* objs,
                              int n_obj, std::uint64_t ts_ns, FsOut* fs,
                              const RoadEdgePoly& road_left, const RoadEdgePoly& road_right,
                              const RoadEdgePoly* hard_walls, int n_hard,
                              const LaneClearFwd* lane_clear) {
  static FsComposeCache cache;

  const float* near_r = nullptr;
  const std::uint8_t* near_ty = nullptr;
  if (near && near->valid) {
    near_r = near->d_r_m;
    near_ty = near->type;
  }
  std::uint32_t fp_b = FsFpRoad(road_left, road_right);
  if (hard_walls && n_hard > 0) {
    for (int h = 0; h < n_hard; ++h) {
      fp_b = FsHashMix(fp_b, FsFpOneRoad(hard_walls[h], static_cast<std::uint32_t>(100 + h)));
    }
  }
  fp_b = FsHashMix(fp_b, static_cast<std::uint32_t>(std::lround(d_empty_cap_m)));
  if (near_r) {
    fp_b = FsHashMix(fp_b, FsFpNear180(near_r, near_ty, kFsEmptyN));
  }
  // lane_clear only feeds d_lane_fwd_m (HUD); not baseline r[] — omit from fp_base.
  const std::uint32_t fp_o = FsFpOcc(objs, n_obj);

  const bool base_dirty = !cache.have || fp_b != cache.fp_base;
  const bool occ_dirty = !cache.have || fp_o != cache.fp_occ || base_dirty;

  if (!base_dirty && !occ_dirty && fs) {
    *fs = {};
    fs->timestamp_ns = ts_ns;
    fs->valid = cache.poly.valid ? 1 : 0;
    fs->n_poly = static_cast<std::uint8_t>(std::min(cache.poly.n, kFsPolyMax));
    for (int i = 0; i < fs->n_poly; ++i) {
      fs->poly_x_m[i] = cache.poly.x[i];
      fs->poly_y_m[i] = cache.poly.y[i];
    }
    if (lane_clear) {
      fs->d_lane_fwd_m[0] = lane_clear->host_m;
      fs->d_lane_fwd_m[1] = lane_clear->left_m;
      fs->d_lane_fwd_m[2] = lane_clear->right_m;
    } else {
      const float fwd = FsDfsFwdFromActive(cache.active);
      fs->d_lane_fwd_m[0] = fwd;
      fs->d_lane_fwd_m[1] = kFsFrontFarCapM;
      fs->d_lane_fwd_m[2] = kFsFrontFarCapM;
    }
    return;
  }

  if (base_dirty) {
    FsBaselineFromOpticsFsd(&cache.baseline, near_r, near_ty, near_r ? kFsEmptyN : 0,
                            d_empty_cap_m);
    FsRestrictLane180(&cache.baseline, road_left, road_right, hard_walls, n_hard);
    // Vertices-in ≠ chord-in on curved LRE; clip rim chords into corridor.
    FsClipEmpty180ChordsToLane(&cache.baseline, road_left, road_right, hard_walls, n_hard);
    cache.fp_base = fp_b;
    std::memset(cache.hit_bins, 0, sizeof(cache.hit_bins));
  }

  if (occ_dirty) {
    FsOccRestoreBins(&cache.active, cache.baseline, base_dirty ? nullptr : cache.hit_bins);
    std::memset(cache.hit_bins, 0, sizeof(cache.hit_bins));
    FsOccApply180(&cache.active, objs, n_obj, cache.hit_bins);
    // Forward chord clip before rear floor — never re-dig after bumper r_min.
    FsClipEmpty180ChordsToLane(&cache.active, road_left, road_right, hard_walls, n_hard);
    // Rear bumper floor: only in rear FOV. Near ±90° cos≈0 ⇒ near_x/cos explodes and
    // would overwrite LRE-clipped side bins (then Pack∩SideLatM puts ymaxL back to 7).
    const float near_x = gf_fs_envelope::kFsEgoRearBumperX;
    for (int i = 0; i < kFsEmptyN; ++i) {
      const float ang = FsBinAngRad(i);
      if (!FsInRearFov(ang)) {
        continue;
      }
      const float c = std::cos(ang);
      if (c >= -1.0e-3f) {
        continue;
      }
      const float r_min = near_x / c;
      if (r_min > 0.5f && r_min < 80.0f && cache.active.r[i] < r_min) {
        cache.active.r[i] = r_min;
      }
    }
    cache.fp_occ = fp_o;
    cache.poly = FsPack180ToPoly(cache.active);
  }

  cache.have = true;
  if (!fs) {
    return;
  }
  *fs = {};
  fs->timestamp_ns = ts_ns;
  fs->valid = cache.poly.valid ? 1 : 0;
  fs->n_poly = static_cast<std::uint8_t>(std::min(cache.poly.n, kFsPolyMax));
  for (int i = 0; i < fs->n_poly; ++i) {
    fs->poly_x_m[i] = cache.poly.x[i];
    fs->poly_y_m[i] = cache.poly.y[i];
  }
  if (lane_clear) {
    fs->d_lane_fwd_m[0] = lane_clear->host_m;
    fs->d_lane_fwd_m[1] = lane_clear->left_m;
    fs->d_lane_fwd_m[2] = lane_clear->right_m;
  } else {
    const float fwd = FsDfsFwdFromActive(cache.active);
    fs->d_lane_fwd_m[0] = fwd;
    fs->d_lane_fwd_m[1] = kFsFrontFarCapM;
    fs->d_lane_fwd_m[2] = kFsFrontFarCapM;
  }
}

}  // namespace gf_plan_fs
