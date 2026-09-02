#include "gf_foxglove/bev_compose.hpp"

#include "gf_foxglove/png.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <string>
#include <utility>
#include <vector>

namespace gf_foxglove {
namespace {

using Buf = std::vector<std::uint8_t>;

void set_pixel(Buf& buf, int w, int h, int x, int y, Rgb rgb) {
  if (x < 0 || y < 0 || x >= w || y >= h) return;
  const std::size_t i = (static_cast<std::size_t>(y) * w + x) * 3;
  buf[i] = rgb.r;
  buf[i + 1] = rgb.g;
  buf[i + 2] = rgb.b;
}

void fill_rect(Buf& buf, int w, int h, int x0, int y0, int x1, int y1, Rgb rgb) {
  for (int y = std::max(0, y0); y < std::min(h, y1); ++y) {
    for (int x = std::max(0, x0); x < std::min(w, x1); ++x) set_pixel(buf, w, h, x, y, rgb);
  }
}

void draw_line(Buf& buf, int w, int h, int x0, int y0, int x1, int y1, Rgb rgb, int thick) {
  const int dx = std::abs(x1 - x0);
  const int dy = std::abs(y1 - y0);
  const int sx = x0 < x1 ? 1 : -1;
  const int sy = y0 < y1 ? 1 : -1;
  int err = dx - dy;
  int x = x0, y = y0;
  const int t0 = -thick / 2;
  const int t1 = thick / 2 + 1;
  while (true) {
    for (int oy = t0; oy < t1; ++oy) {
      for (int ox = t0; ox < t1; ++ox) set_pixel(buf, w, h, x + ox, y + oy, rgb);
    }
    if (x == x1 && y == y1) break;
    const int e2 = 2 * err;
    if (e2 > -dy) {
      err -= dy;
      x += sx;
    }
    if (e2 < dx) {
      err += dx;
      y += sy;
    }
  }
}

void fill_convex_poly(Buf& buf, int w, int h, const std::vector<std::pair<int, int>>& pts, Rgb fill,
                      const Rgb* outline, int y_clip0) {
  const int n = static_cast<int>(pts.size());
  if (n < 3) return;
  std::vector<std::vector<float>> xs_at(h);
  bool any = false;
  for (int i = 0; i < n; ++i) {
    int x0 = pts[i].first, y0 = pts[i].second;
    int x1 = pts[(i + 1) % n].first, y1 = pts[(i + 1) % n].second;
    if (y0 == y1) continue;
    if (y0 > y1) {
      std::swap(x0, x1);
      std::swap(y0, y1);
    }
    const int y_lo = std::max(y_clip0, y0);
    const int y_hi = std::min(h - 1, y1);
    if (y_hi < y_lo) continue;
    const float dy = static_cast<float>(y1 - y0);
    for (int y = y_lo; y <= y_hi; ++y) {
      float t = (static_cast<float>(y) - y0) / dy;
      t = std::max(0.0f, std::min(1.0f, t));
      xs_at[y].push_back(x0 + t * (x1 - x0));
      any = true;
    }
  }
  if (!any) {
    int xa = w, xb = 0, ya = h, yb = 0;
    for (const auto& p : pts) {
      xa = std::min(xa, p.first);
      xb = std::max(xb, p.first);
      ya = std::min(ya, p.second);
      yb = std::max(yb, p.second);
    }
    fill_rect(buf, w, h, std::max(0, xa), std::max(y_clip0, ya), std::min(w, xb + 1),
              std::min(h, yb + 1), fill);
  } else {
    for (int y = 0; y < h; ++y) {
      if (xs_at[y].empty()) continue;
      float mn = xs_at[y][0], mx = xs_at[y][0];
      for (float v : xs_at[y]) {
        mn = std::min(mn, v);
        mx = std::max(mx, v);
      }
      const int xa = std::max(0, static_cast<int>(std::floor(mn)));
      const int xb = std::min(w - 1, static_cast<int>(std::ceil(mx)));
      if (xa <= xb) fill_rect(buf, w, h, xa, y, xb + 1, y + 1, fill);
    }
  }
  if (outline) {
    for (int i = 0; i < n; ++i) {
      draw_line(buf, w, h, pts[i].first, pts[i].second, pts[(i + 1) % n].first,
                pts[(i + 1) % n].second, *outline, 2);
    }
  }
}

struct Vec3 {
  float x, y, z;
};

Vec3 vsub(Vec3 a, Vec3 b) { return {a.x - b.x, a.y - b.y, a.z - b.z}; }
float vdot(Vec3 a, Vec3 b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
Vec3 vcross(Vec3 a, Vec3 b) {
  return {a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x};
}
Vec3 vnorm(Vec3 a) {
  const float n = std::sqrt(vdot(a, a));
  const float d = n > 0 ? n : 1.0f;
  return {a.x / d, a.y / d, a.z / d};
}

struct BevCam {
  float ox, oy_pp, f;
  Vec3 cpos, right, up, fwd;
  std::pair<int, int> project(float x, float y, float z) const {
    const Vec3 rel{x - cpos.x, y - cpos.y, z - cpos.z};
    const float xc = vdot(rel, right);
    const float yc = vdot(rel, up);
    const float zc = std::max(0.85f, vdot(rel, fwd));
    const float u = ox + f * xc / zc;
    const float v = oy_pp - f * yc / zc;
    return {static_cast<int>(std::lround(u)), static_cast<int>(std::lround(v))};
  }
};

void cam_basis(Vec3* cpos, Vec3* right, Vec3* up, Vec3* fwd) {
  *cpos = {-kBevCamBackM, 0.0f, kBevCamHeightM};
  const Vec3 tgt{kBevCamLookM, 0.0f, 0.0f};
  *fwd = vnorm(vsub(tgt, *cpos));
  *right = vnorm(vcross(*fwd, {0, 0, 1}));
  if (std::fabs(vdot(*right, *right)) < 1e-8f) *right = {0, -1, 0};
  *up = vnorm(vcross(*right, *fwd));
}

BevCam make_bev_cam(int width, int height) {
  const float ox = static_cast<float>(width) * 0.5f;
  const float oy_ego = static_cast<float>(height) - 44.0f;
  const float y_far = 32.0f;
  Vec3 cpos, right, up, fwd;
  cam_basis(&cpos, &right, &up, &fwd);
  auto yz = [&](float x, float y, float z) {
    const Vec3 rel{x - cpos.x, y - cpos.y, z - cpos.z};
    return std::pair<float, float>{vdot(rel, up), std::max(0.85f, vdot(rel, fwd))};
  };
  const auto a0p = yz(0, 0, 0);
  const auto a1p = yz(kDBevM, 0, 0);
  const float a0 = a0p.first / a0p.second;
  const float a1 = a1p.first / a1p.second;
  const float den = a0 - a1;
  float f, oy_pp;
  if (std::fabs(den) < 1e-6f) {
    f = 420.0f;
    oy_pp = oy_ego;
  } else {
    f = (y_far - oy_ego) / den;
    if (f < 40.0f) f = 420.0f;
    oy_pp = oy_ego + f * a0;
  }
  return BevCam{ox, oy_pp, f, cpos, right, up, fwd};
}

float obj_height_m(int obj_class) {
  if (obj_class == 5) return 1.7f;
  if (obj_class == 2) return 3.0f;
  if (obj_class == 3 || obj_class == 4 || obj_class == 9) return 1.4f;
  return 1.5f;
}

float lon_intent(const LiveBevState& st) {
  const float thr = std::max(0.0f, std::min(1.0f, st.throttle_cmd));
  const float brk = std::max(0.0f, std::min(1.0f, st.brake_cmd));
  if (thr > 0.04f || brk > 0.04f) return std::max(-1.0f, std::min(1.0f, thr - brk));
  return std::max(-1.0f, std::min(1.0f, st.lon_accel_mps2 / 2.5f));
}

Rgb traj_color_for_lon(const LiveBevState& st) {
  const float intent = lon_intent(st);
  if (intent > 0.08f) return {70, 210, 110};
  if (intent < -0.08f) return {230, 80, 80};
  return {90, 160, 255};
}

int traj_thickness_for_lon(const LiveBevState& st) {
  const float intent = std::fabs(lon_intent(st));
  if (intent <= 0.08f) return 2;
  return std::max(3, std::min(7, 2 + static_cast<int>(std::lround(intent * 5.0f))));
}

int traj_seg_thickness(float v0, float v1) {
  const float dv = v1 - v0;
  if (dv < -1.0f) return 5;
  if (dv > 1.0f) return 4;
  return 3;
}

// 5×7 column bitmaps (LSB = top).
const std::uint8_t* font5(char ch) {
  static const std::uint8_t z[5] = {0x3E, 0x45, 0x49, 0x51, 0x3E};
  static const std::uint8_t c1[5] = {0x00, 0x21, 0x7F, 0x01, 0x00};
  static const std::uint8_t c2[5] = {0x21, 0x43, 0x45, 0x49, 0x31};
  static const std::uint8_t c3[5] = {0x42, 0x41, 0x51, 0x69, 0x46};
  static const std::uint8_t c4[5] = {0x0C, 0x14, 0x24, 0x7F, 0x04};
  static const std::uint8_t c5[5] = {0x72, 0x51, 0x51, 0x51, 0x4E};
  static const std::uint8_t c6[5] = {0x3E, 0x49, 0x49, 0x49, 0x26};
  static const std::uint8_t c7[5] = {0x40, 0x47, 0x48, 0x50, 0x60};
  static const std::uint8_t c8[5] = {0x36, 0x49, 0x49, 0x49, 0x36};
  static const std::uint8_t c9[5] = {0x32, 0x49, 0x49, 0x49, 0x3E};
  static const std::uint8_t dot[5] = {0x00, 0x00, 0x03, 0x00, 0x00};
  static const std::uint8_t sp[5] = {0, 0, 0, 0, 0};
  static const std::uint8_t V[5] = {0x7C, 0x02, 0x01, 0x02, 0x7C};
  static const std::uint8_t D[5] = {0x7F, 0x41, 0x41, 0x41, 0x3E};
  static const std::uint8_t T[5] = {0x40, 0x40, 0x7F, 0x40, 0x40};
  static const std::uint8_t L[5] = {0x7F, 0x01, 0x01, 0x01, 0x01};
  static const std::uint8_t C[5] = {0x3E, 0x41, 0x41, 0x41, 0x22};
  switch (ch) {
    case '0':
      return z;
    case '1':
      return c1;
    case '2':
      return c2;
    case '3':
      return c3;
    case '4':
      return c4;
    case '5':
      return c5;
    case '6':
      return c6;
    case '7':
      return c7;
    case '8':
      return c8;
    case '9':
      return c9;
    case '.':
      return dot;
    case 'V':
      return V;
    case 'D':
      return D;
    case 'T':
      return T;
    case 'L':
      return L;
    case 'C':
      return C;
    default:
      return sp;
  }
}

void blit_text(Buf& buf, int w, int h, int x, int y, const char* text, Rgb rgb, int scale) {
  int cx = x;
  const int sc = std::max(1, scale);
  for (const char* p = text; *p; ++p) {
    char ch = *p;
    if (ch >= 'a' && ch <= 'z') ch = static_cast<char>(ch - 'a' + 'A');
    const std::uint8_t* cols = font5(ch);
    for (int ci = 0; ci < 5; ++ci) {
      for (int row = 0; row < 7; ++row) {
        if (cols[ci] & (1 << row)) {
          fill_rect(buf, w, h, cx + ci * sc, y + row * sc, cx + ci * sc + sc, y + row * sc + sc,
                    rgb);
        }
      }
    }
    cx += (5 + 1) * sc;
  }
}

float optical_d_along_poly(float c0, float c1, float c2, float c3, float x_end) {
  float d = std::min(120.0f, x_end > 0.5f ? x_end : 120.0f);
  const float half = 0.5f * (kSeeFovDeg * 3.14159265358979323846f / 180.0f);
  for (float x = 2.0f; x <= d + 1e-6f; x += 2.0f) {
    const float y = c0 + c1 * x + c2 * x * x + c3 * x * x * x;
    if (std::fabs(std::atan2(y, x)) > half) return x;
  }
  return d;
}

const Rgb kIdPalette[] = {
    {220, 90, 90},   {90, 180, 220},  {220, 180, 60},  {180, 100, 220}, {60, 200, 160},
    {230, 140, 80},  {100, 140, 230}, {200, 80, 160},  {140, 200, 80},  {80, 200, 220},
    {230, 100, 120}, {160, 160, 90},
};

}  // namespace

bool dash_lit_m(float s_m, float scroll_m) {
  float u = std::fmod(s_m + scroll_m, kDashPeriodM);
  if (u < 0.0f) u += kDashPeriodM;
  return u < kDashOnM;
}

Rgb color_for_obj_id(int obj_id) {
  if (obj_id <= 0) return kIdPalette[0];
  return kIdPalette[(obj_id - 1) % 12];
}

Rgb traj_color_for_v(float v, float v_hi) {
  const float t = std::max(0.0f, std::min(1.0f, v / std::max(v_hi, 1.0f)));
  if (t < 0.45f) {
    const float u = t / 0.45f;
    return {static_cast<std::uint8_t>(220 + (230 - 220) * u),
            static_cast<std::uint8_t>(70 + (180 - 70) * u),
            static_cast<std::uint8_t>(70 + (60 - 70) * u)};
  }
  const float u = (t - 0.45f) / 0.55f;
  return {static_cast<std::uint8_t>(230 + (70 - 230) * u),
          static_cast<std::uint8_t>(180 + (210 - 180) * u),
          static_cast<std::uint8_t>(60 + (110 - 60) * u)};
}

float see_opening_m(float host_vr_m, const LiveBevState& st) {
  float opening = std::max(0.0f, host_vr_m);
  const float lat_max = std::max(0.8f, kSeeHostLatM);
  for (int i = 0; i < st.n_obj; ++i) {
    const float x = st.perc_objects[i].x_m;
    const float y = st.perc_objects[i].y_m;
    if (x <= 0.5f || x >= opening) continue;
    if (std::fabs(y) > lat_max) continue;
    opening = x;
  }
  return opening;
}

float driving_see_m(const LiveBevState& st, float host_vr_m) {
  if (st.traj_d_see_m > 0.5f) return st.traj_d_see_m;
  const float occ = see_opening_m(host_vr_m, st);
  const float vr = std::max(0.0f, host_vr_m);
  if (st.n_host <= 0) return std::min(occ, vr);
  float c0 = 0, c1 = 0, c2 = 0, c3 = 0;
  for (int i = 0; i < st.n_host; ++i) {
    c0 += st.host_lanes[i].c0;
    c1 += st.host_lanes[i].c1;
    c2 += st.host_lanes[i].c2;
    c3 += st.host_lanes[i].c3;
  }
  const float n = static_cast<float>(st.n_host);
  const float opt = optical_d_along_poly(c0 / n, c1 / n, c2 / n, c3 / n, vr > 0.5f ? vr : 120.0f);
  return std::min(occ, opt);
}

void advance_odom(LiveBevState& st, std::uint64_t t_ns, float speed_mps) {
  if (t_ns == 0) return;
  if (st.last_t_ns > 0 && t_ns > st.last_t_ns) {
    double dt = static_cast<double>(t_ns - st.last_t_ns) / 1e9;
    dt = std::min(dt, 0.5);
    st.odom_m += std::max(0.0f, speed_mps) * static_cast<float>(dt);
    if (dt >= 0.02) {
      float raw_a = (speed_mps - st.last_speed_mps) / static_cast<float>(dt);
      raw_a = std::max(-6.0f, std::min(6.0f, raw_a));
      st.lon_accel_mps2 = 0.65f * st.lon_accel_mps2 + 0.35f * raw_a;
    }
  } else if (st.last_t_ns == 0) {
    st.odom_m += std::max(0.0f, speed_mps) * 0.05f;
  }
  st.last_t_ns = t_ns;
  st.last_speed_mps = speed_mps;
}

std::string render_ego_bev_png(const LiveBevState& st, int width, int height) {
  const Rgb bg{24, 28, 36};
  const Rgb lh_c{235, 235, 250};
  const Rgb la_c{170, 175, 190};
  const Rgb dash_c{200, 200, 90};
  const Rgb ego_c{80, 200, 120};
  const Rgb uss_c{220, 180, 60};
  const Rgb text_bar{40, 44, 55};
  const Rgb tick_c{168, 168, 172};
  const Rgb tick_major_c{200, 200, 204};
  const Rgb cipv_outline{245, 245, 250};

  Buf buf(static_cast<std::size_t>(width) * height * 3);
  for (std::size_t i = 0; i < buf.size(); i += 3) {
    buf[i] = bg.r;
    buf[i + 1] = bg.g;
    buf[i + 2] = bg.b;
  }
  fill_rect(buf, width, height, 0, 0, width, 28, text_bar);

  const BevCam cam = make_bev_cam(width, height);
  const float lane_w = st.lane_width_m > 0.5f ? st.lane_width_m : 3.5f;
  const float half = 0.5f * lane_w;

  const HostLanePoly* left_poly = nullptr;
  const HostLanePoly* right_poly = nullptr;
  for (int i = 0; i < st.n_host; ++i) {
    if (st.host_lanes[i].side == 1) left_poly = &st.host_lanes[i];
    else if (st.host_lanes[i].side == 2)
      right_poly = &st.host_lanes[i];
  }
  if (!left_poly && st.n_host > 0) left_poly = &st.host_lanes[0];
  if (!right_poly && st.n_host > 1) right_poly = &st.host_lanes[1];

  float c1_ref = 0;
  if (left_poly && right_poly) c1_ref = 0.5f * (left_poly->c1 + right_poly->c1);
  else if (left_poly)
    c1_ref = left_poly->c1;
  else if (right_poly)
    c1_ref = right_poly->c1;
  else if (st.n_host > 0)
    c1_ref = st.host_lanes[0].c1;
  else if (st.n_adj > 0)
    c1_ref = st.adj_lanes[0].c1;
  const float psi = std::atan(std::max(-4.0f, std::min(4.0f, c1_ref)));
  const float c_psi = std::cos(psi);
  const float s_psi = std::sin(psi);

  auto ego_to_road = [&](float xe, float ye) {
    return std::pair<float, float>{xe * c_psi + ye * s_psi, -xe * s_psi + ye * c_psi};
  };
  auto host_y_ego = [&](float xe, char side) {
    if (side == 'l' && left_poly) return left_poly->y_at(xe);
    if (side == 'r' && right_poly) return right_poly->y_at(xe);
    return side == 'l' ? half : -half;
  };

  std::vector<float> y_road_samples;
  for (float xe_s : {0.0f, 2.0f, 5.0f}) {
    for (char side : {'l', 'r'}) {
      y_road_samples.push_back(ego_to_road(xe_s, host_y_ego(xe_s, side)).second);
    }
    for (int i = 0; i < st.n_host; ++i)
      y_road_samples.push_back(ego_to_road(xe_s, st.host_lanes[i].y_at(xe_s)).second);
    for (int i = 0; i < st.n_adj; ++i)
      y_road_samples.push_back(ego_to_road(xe_s, st.adj_lanes[i].y_at(xe_s)).second);
  }
  float y_span_min = -half, y_span_max = half;
  if (!y_road_samples.empty()) {
    y_span_min = *std::min_element(y_road_samples.begin(), y_road_samples.end());
    y_span_max = *std::max_element(y_road_samples.begin(), y_road_samples.end());
  }
  const float y_mid = 0.5f * (y_span_min + y_span_max);
  const float scroll = std::fmod(st.odom_m, kDashPeriodM);

  float host_vr = kDBevM;
  if (st.n_host > 0) {
    host_vr = kDBevM;
    for (int i = 0; i < st.n_host; ++i) host_vr = std::min(host_vr, st.host_lanes[i].x1);
    host_vr = std::min(kDBevM, host_vr);
  }
  const float x_draw = std::max(0.0f, host_vr);
  const float tick_stub_m = 0.55f;

  auto e2p_road = [&](float xr, float yr, float zr = 0.0f) {
    return cam.project(xr, yr - y_mid, zr);
  };
  auto e2p_ego = [&](float xe, float ye, float zr = 0.0f) {
    auto rr = ego_to_road(xe, ye);
    return e2p_road(rr.first, rr.second, zr);
  };

  auto draw_poly = [&](auto&& poly, Rgb color, int thick, bool dashed) {
    const float x_hi = std::min(poly.x1, x_draw);
    const float x_lo = std::max(0.0f, poly.x0);
    if (x_hi <= x_lo + 0.25f) return;
    int px = 0, py = 0;
    bool have_prev = false, prev_lit = false;
    const float span = x_hi - x_lo;
    const int steps = std::max(48, static_cast<int>(span * 2) + 1);
    for (int i = 0; i <= steps; ++i) {
      const float xe = x_lo + span * static_cast<float>(i) / static_cast<float>(steps);
      if (xe > poly.x1 + 1e-3f) break;
      const float ye = poly.y_at(xe);
      const auto rr = ego_to_road(xe, ye);
      if (rr.first < -2.0f || rr.first > x_draw + 5.0f) {
        have_prev = false;
        continue;
      }
      const auto pt = e2p_road(rr.first, rr.second);
      const bool lit = (!dashed) || dash_lit_m(xe, scroll);
      if (have_prev && lit && prev_lit) {
        draw_line(buf, width, height, px, py, pt.first, pt.second, color, thick);
      }
      px = pt.first;
      py = pt.second;
      have_prev = true;
      prev_lit = lit;
    }
  };

  float d_see = 0;
  if (st.n_host > 0) {
    bool any = false;
    for (int i = 0; i < st.n_host; ++i) {
      if (st.host_lanes[i].x1 > 0.5f) {
        d_see = any ? std::min(d_see, st.host_lanes[i].x1) : st.host_lanes[i].x1;
        any = true;
      }
    }
  }
  const float occupy_open = see_opening_m(d_see, st);
  const float opening = driving_see_m(st, d_see);

  for (int i = 0; i < st.n_host; ++i)
    draw_poly(st.host_lanes[i], lh_c, 3, st.host_lanes[i].is_dashed());
  for (int i = 0; i < st.n_adj; ++i)
    draw_poly(st.adj_lanes[i], la_c, 2, st.adj_lanes[i].is_dashed());

  if (x_draw > 0.5f && st.n_host > 0) {
    const float y_host_mid_e = 0.5f * (host_y_ego(0.0f, 'l') + host_y_ego(0.0f, 'r'));
    auto pt_at_road_x = [&](float xr) {
      const float xe = xr * c_psi;
      const float ye = 0.5f * (host_y_ego(xe, 'l') + host_y_ego(xe, 'r'));
      return e2p_ego(xe, ye);
    };
    const int k0 = static_cast<int>(std::floor((-kDashPeriodM - scroll) / kDashPeriodM));
    const int k1 = static_cast<int>(std::ceil((x_draw + kDashPeriodM - scroll) / kDashPeriodM));
    for (int k = k0; k <= k1; ++k) {
      const float x0 = static_cast<float>(k) * kDashPeriodM - scroll;
      const float x1 = x0 + kDashOnM;
      if (x1 < 0.0f || x0 > x_draw) continue;
      const auto p0 = pt_at_road_x(std::max(0.0f, x0));
      const auto p1 = pt_at_road_x(std::min(x_draw, x1));
      draw_line(buf, width, height, p0.first, p0.second, p1.first, p1.second, dash_c, 2);
    }

    auto corridor_yr = [&](float xr_t) {
      float xe = xr_t * c_psi;
      for (int it = 0; it < 3; ++it) {
        const float ye_mid = 0.5f * (host_y_ego(xe, 'l') + host_y_ego(xe, 'r'));
        const float xr_now = ego_to_road(xe, ye_mid).first;
        xe += (xr_t - xr_now) * c_psi;
      }
      std::vector<float> ys;
      for (int i = 0; i < st.n_host; ++i) {
        ys.push_back(
            ego_to_road(xe, st.host_lanes[i].y_at(std::min(xe, st.host_lanes[i].x1))).second);
      }
      for (int i = 0; i < st.n_adj; ++i) {
        ys.push_back(ego_to_road(xe, st.adj_lanes[i].y_at(std::min(xe, st.adj_lanes[i].x1))).second);
      }
      if (ys.empty()) {
        ys.push_back(ego_to_road(xe, host_y_ego(xe, 'l')).second);
        ys.push_back(ego_to_road(xe, host_y_ego(xe, 'r')).second);
      }
      return std::pair<float, float>{*std::min_element(ys.begin(), ys.end()),
                                    *std::max_element(ys.begin(), ys.end())};
    };
    const auto y0s = corridor_yr(0.0f);
    const float yr_host = ego_to_road(0.0f, y_host_mid_e).second;
    const bool use_left_outer = std::fabs(y0s.second - yr_host) <= std::fabs(y0s.first - yr_host);
    for (int k = 0; k <= static_cast<int>(x_draw) / 20; ++k) {
      const float xr = static_cast<float>(k * 20);
      if (xr <= 0.0f || xr > x_draw) continue;
      const auto ys = corridor_yr(xr);
      float y_edge, y_tip;
      if (use_left_outer) {
        y_edge = ys.second;
        y_tip = y_edge + tick_stub_m * (k % 2 == 0 ? 1.35f : 0.85f);
      } else {
        y_edge = ys.first;
        y_tip = y_edge - tick_stub_m * (k % 2 == 0 ? 1.35f : 0.85f);
      }
      const bool major = (k % 2 == 0);
      const auto p0 = e2p_road(xr, y_edge);
      const auto p1 = e2p_road(xr, y_tip);
      draw_line(buf, width, height, p0.first, p0.second, p1.first, p1.second,
                major ? tick_major_c : tick_c, major ? 2 : 1);
    }
  }

  if (st.n_traj >= 2) {
    const int nseg = st.n_traj - 1;
    const bool has_v = st.n_traj_v >= nseg + 1;
    float v_hi = 12.0f;
    if (has_v) {
      for (int i = 0; i <= nseg && i < st.n_traj_v; ++i) v_hi = std::max(v_hi, st.traj_v[i]);
    }
    const Rgb fallback_c = traj_color_for_lon(st);
    const int fallback_th = traj_thickness_for_lon(st);
    const float x_hi = occupy_open > 0.5f ? occupy_open : x_draw;
    for (int i = 0; i < nseg; ++i) {
      float x0 = st.traj_x[i], y0 = st.traj_y[i];
      float x1 = st.traj_x[i + 1], y1 = st.traj_y[i + 1];
      if (std::min(x0, x1) > x_hi) break;
      if (x1 > x_hi && x1 > x0 + 1e-6f) {
        const float t = (x_hi - x0) / (x1 - x0);
        y1 = y0 + t * (y1 - y0);
        x1 = x_hi;
      }
      const auto a = e2p_ego(x0, y0);
      const auto b = e2p_ego(x1, y1);
      Rgb col = fallback_c;
      int th = fallback_th;
      if (has_v) {
        const float v0 = st.traj_v[i];
        const float v1 = st.traj_v[std::min(i + 1, st.n_traj_v - 1)];
        col = traj_color_for_v(0.5f * (v0 + v1), v_hi);
        th = traj_seg_thickness(v0, v1);
      }
      draw_line(buf, width, height, a.first, a.second, b.first, b.second, col, th);
    }
  }

  if (st.nearest_cm > 0) {
    const float dist_m = std::max(0.5f, std::min(st.nearest_cm / 100.0f, kDBevM));
    const auto cxy = e2p_ego(dist_m, 0.0f);
    fill_rect(buf, width, height, cxy.first - 4, cxy.second - 4, cxy.first + 4, cxy.second + 4,
              uss_c);
  }

  auto paint_box = [&](float xe, float ye, float length_m, float width_m, float heading_ego,
                       Rgb fill, const Rgb* outline, float height_m) {
    const auto rr = ego_to_road(xe, ye);
    const float heading_r = heading_ego - psi;
    const float c = std::cos(heading_r);
    const float s = std::sin(heading_r);
    const float hl = 0.5f * std::max(length_m, 1.2f);
    const float hw = 0.5f * std::max(width_m, 1.0f);
    const float hh = std::max(0.6f, height_m);
    const std::pair<float, float> corners[4] = {
        {rr.first + hl * c - hw * s, rr.second + hl * s + hw * c},
        {rr.first + hl * c + hw * s, rr.second + hl * s - hw * c},
        {rr.first - hl * c + hw * s, rr.second - hl * s - hw * c},
        {rr.first - hl * c - hw * s, rr.second - hl * s + hw * c},
    };
    std::vector<std::pair<int, int>> bot(4), top(4);
    for (int i = 0; i < 4; ++i) {
      bot[i] = e2p_road(corners[i].first, corners[i].second, 0.0f);
      top[i] = e2p_road(corners[i].first, corners[i].second, hh);
    }
    const Rgb shade{static_cast<std::uint8_t>(fill.r * 0.55f),
                    static_cast<std::uint8_t>(fill.g * 0.55f),
                    static_cast<std::uint8_t>(fill.b * 0.55f)};
    fill_convex_poly(buf, width, height, bot, shade, nullptr, 28);
    for (int i = 0; i < 4; ++i) {
      std::vector<std::pair<int, int>> side = {bot[i], bot[(i + 1) % 4], top[(i + 1) % 4], top[i]};
      fill_convex_poly(buf, width, height, side, fill, nullptr, 28);
    }
    fill_convex_poly(buf, width, height, top, fill, outline, 28);
  };

  const int n_paint = st.n_obj;
  for (int i = 0; i < n_paint; ++i) {
    const auto& obj = st.perc_objects[i];
    const float xr = ego_to_road(obj.x_m, obj.y_m).first;
    if (obj.x_m < -2.0f || xr > kDBevM + 5.0f) continue;
    Rgb fill = color_for_obj_id(obj.obj_id);
    if (obj.obj_class == 5) fill = {220, 160, 80};
    const Rgb* ol = obj.is_cipv ? &cipv_outline : nullptr;
    paint_box(obj.x_m, obj.y_m, obj.length_m, obj.width_m, obj.heading_rad, fill, ol,
              obj_height_m(obj.obj_class));
  }
  if (n_paint == 0 && (st.has_perc_lead || st.lead_dist_m > 0.5f)) {
    paint_box(st.cipo_x_m > 0.5f ? st.cipo_x_m : st.lead_dist_m, st.cipo_y_m, 4.5f, 1.8f, 0.0f,
              color_for_obj_id(st.cipv_id ? st.cipv_id : 1), &cipv_outline, 1.5f);
  }

  paint_box(0.0f, 0.0f, 4.5f, 1.8f, 0.0f, ego_c, nullptr, 1.5f);

  const int bar_w = std::min(120, std::max(8, static_cast<int>(st.speed_mps * 6)));
  fill_rect(buf, width, height, 8, 6, 8 + bar_w, 14, {80, 180, 90});
  float v_plan = st.traj_v_plan_mps;
  if (v_plan <= 0.0f && st.n_traj_v > 0) v_plan = st.traj_v[0];
  const int plan_w = std::min(120, std::max(4, static_cast<int>(v_plan * 6)));
  fill_rect(buf, width, height, 8, 15, 8 + plan_w, 22, {80, 190, 210});
  const int spark = 8 + static_cast<int>(st.odom_m * 10) % std::max(1, width - 16);
  fill_rect(buf, width, height, spark, 6, spark + 3, 22, {240, 240, 80});

  char hud[80];
  std::snprintf(hud, sizeof(hud), "V%4.1f D%3.0f T%3.1f%s", static_cast<double>(v_plan),
                static_cast<double>(opening), static_cast<double>(st.traj_t_plan_s),
                st.allow_lc ? " LC" : "");
  blit_text(buf, width, height, 140, 7, hud, {220, 224, 230}, 1);

  return png_rgb(width, height, buf.data());
}

}  // namespace gf_foxglove
