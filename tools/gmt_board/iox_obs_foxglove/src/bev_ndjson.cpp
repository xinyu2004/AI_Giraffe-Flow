#include "gf_foxglove/bev_ndjson.hpp"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

namespace gf_foxglove {
namespace {

const char* skip_ws(const char* p, const char* end) {
  while (p < end && std::isspace(static_cast<unsigned char>(*p))) ++p;
  return p;
}

// Find `"key"` then `:` then value start. Returns pointer at value, or nullptr.
const char* find_key(const char* begin, const char* end, const char* key) {
  const std::size_t klen = std::strlen(key);
  const char* p = begin;
  while (p + klen + 3 < end) {
    const char* q = static_cast<const char*>(std::memchr(p, '"', static_cast<std::size_t>(end - p)));
    if (!q) return nullptr;
    if (static_cast<std::size_t>(end - q) > klen + 1 &&
        std::memcmp(q + 1, key, klen) == 0 && q[1 + klen] == '"') {
      const char* r = skip_ws(q + 2 + klen, end);
      if (r < end && *r == ':') return skip_ws(r + 1, end);
    }
    p = q + 1;
  }
  return nullptr;
}

// Object slice that contains key at top level of `obj` (obj points at '{').
bool object_span(const char* obj, const char* end, const char** out_b, const char** out_e) {
  if (!obj || obj >= end || *obj != '{') return false;
  int depth = 0;
  bool in_str = false;
  bool esc = false;
  for (const char* p = obj; p < end; ++p) {
    const char c = *p;
    if (in_str) {
      if (esc) {
        esc = false;
      } else if (c == '\\') {
        esc = true;
      } else if (c == '"') {
        in_str = false;
      }
      continue;
    }
    if (c == '"') {
      in_str = true;
      continue;
    }
    if (c == '{') ++depth;
    else if (c == '}') {
      --depth;
      if (depth == 0) {
        *out_b = obj;
        *out_e = p + 1;
        return true;
      }
    }
  }
  return false;
}

bool array_span(const char* arr, const char* end, const char** out_b, const char** out_e) {
  if (!arr || arr >= end || *arr != '[') return false;
  int depth = 0;
  bool in_str = false;
  bool esc = false;
  for (const char* p = arr; p < end; ++p) {
    const char c = *p;
    if (in_str) {
      if (esc) esc = false;
      else if (c == '\\') esc = true;
      else if (c == '"') in_str = false;
      continue;
    }
    if (c == '"') {
      in_str = true;
      continue;
    }
    if (c == '[') ++depth;
    else if (c == ']') {
      --depth;
      if (depth == 0) {
        *out_b = arr;
        *out_e = p + 1;
        return true;
      }
    }
  }
  return false;
}

bool get_number(const char* begin, const char* end, const char* key, double* out) {
  const char* v = find_key(begin, end, key);
  if (!v) return false;
  char* ep = nullptr;
  const double x = std::strtod(v, &ep);
  if (ep == v) return false;
  *out = x;
  return true;
}

bool get_boolish(const char* begin, const char* end, const char* key, bool* out) {
  const char* v = find_key(begin, end, key);
  if (!v) return false;
  if (v + 4 <= end && std::memcmp(v, "true", 4) == 0) {
    *out = true;
    return true;
  }
  if (v + 5 <= end && std::memcmp(v, "false", 5) == 0) {
    *out = false;
    return true;
  }
  double x = 0;
  if (get_number(begin, end, key, &x)) {
    *out = (x != 0.0);
    return true;
  }
  return false;
}

bool get_string_leaf(const char* begin, const char* end, const char* key, std::string* out) {
  const char* v = find_key(begin, end, key);
  if (!v || *v != '"') return false;
  ++v;
  std::string s;
  while (v < end && *v != '"') {
    if (*v == '\\' && v + 1 < end) {
      s.push_back(v[1]);
      v += 2;
      continue;
    }
    s.push_back(*v++);
  }
  *out = std::move(s);
  return true;
}

int parse_float_array(const char* begin, const char* end, float* dst, int max_n) {
  const char *ab = nullptr, *ae = nullptr;
  if (!array_span(begin, end, &ab, &ae)) return 0;
  int n = 0;
  const char* p = ab + 1;
  while (p < ae - 1 && n < max_n) {
    p = skip_ws(p, ae);
    if (p >= ae - 1 || *p == ']') break;
    char* ep = nullptr;
    const float x = static_cast<float>(std::strtod(p, &ep));
    if (ep == p) break;
    dst[n++] = x;
    p = ep;
    p = skip_ws(p, ae);
    if (p < ae && *p == ',') ++p;
  }
  return n;
}

bool lane_ok(float conf, int avail, bool has_avail) {
  if (!has_avail) avail = conf >= 0.15f ? 2 : 0;
  return avail != 0 && conf >= 0.15f;
}

void apply_ego(LiveBevState& st, const char* b, const char* e) {
  double x = 0;
  if (get_number(b, e, "timestamp_ns", &x) && x > 0) st.t_ns = static_cast<std::uint64_t>(x);
  if (get_number(b, e, "speed_mps", &x)) st.speed_mps = static_cast<float>(x);
  if (get_number(b, e, "yaw_rate_degps", &x)) st.yaw_rate_degps = static_cast<float>(x);
  if (get_number(b, e, "steer_angle_deg", &x)) st.steer_angle_deg = static_cast<float>(x);
  if (get_number(b, e, "gear", &x)) st.gear = static_cast<int>(x);
  advance_odom(st, st.t_ns, st.speed_mps);
}

void apply_traj(LiveBevState& st, const char* b, const char* e) {
  double x = 0;
  if (get_number(b, e, "timestamp_ns", &x) && x > 0) st.t_ns = static_cast<std::uint64_t>(x);
  const char* vx = find_key(b, e, "points_x_m");
  const char* vy = find_key(b, e, "points_y_m");
  const char* vv = find_key(b, e, "points_v_mps");
  float xs[kMaxTrajPts]{};
  float ys[kMaxTrajPts]{};
  float vs[kMaxTrajPts]{};
  int nx = 0, ny = 0, nv = 0;
  if (vx) nx = parse_float_array(vx, e, xs, kMaxTrajPts);
  if (vy) ny = parse_float_array(vy, e, ys, kMaxTrajPts);
  if (vv) nv = parse_float_array(vv, e, vs, kMaxTrajPts);
  int n = std::min(nx, ny);
  n = std::max(0, std::min(n, kMaxTrajPts));
  st.n_traj = n;
  st.n_traj_v = std::min(n, nv);
  for (int i = 0; i < n; ++i) {
    st.traj_x[i] = xs[i];
    st.traj_y[i] = ys[i];
    st.traj_v[i] = (i < nv) ? vs[i] : 0.f;
  }
  if (get_number(b, e, "throttle", &x)) st.throttle_cmd = static_cast<float>(x);
  if (get_number(b, e, "brake", &x)) st.brake_cmd = static_cast<float>(x);
  if (get_number(b, e, "target_speed_mps", &x)) st.traj_v_plan_mps = static_cast<float>(x);
  if (get_number(b, e, "D_see_m", &x)) st.traj_d_see_m = static_cast<float>(x);
  if (get_number(b, e, "T_plan_s", &x)) st.traj_t_plan_s = static_cast<float>(x);
  if (get_number(b, e, "horizon_m", &x)) st.traj_horizon_m = static_cast<float>(x);
  if (get_number(b, e, "s_stop_m", &x)) st.traj_s_stop_m = static_cast<float>(x);
  if (get_number(b, e, "v_sign_max_mps", &x)) st.v_sign_max_mps = static_cast<float>(x);
  if (get_number(b, e, "v_sign_min_mps", &x)) st.v_sign_min_mps = static_cast<float>(x);
  bool lc = false;
  if (get_boolish(b, e, "allow_lc", &lc)) st.allow_lc = lc;
  if (get_number(b, e, "cipv_long_m", &x) && x > 0.5) {
    st.has_perc_lead = true;
    st.lead_dist_m = static_cast<float>(x);
    st.cipo_x_m = static_cast<float>(x);
  }
}

void apply_host_lines(LiveBevState& st, const char* lh_b, const char* lh_e) {
  st.n_host = 0;
  double w = 0;
  if (get_number(lh_b, lh_e, "m_LH_Estimated_Width", &w) && w > 0.5) {
    st.lane_width_m = static_cast<float>(w);
  }
  const char* items = find_key(lh_b, lh_e, "m_hostline");
  if (!items || *items != '[') {
    st.has_perc_lanes = false;
    return;
  }
  const char *ab = nullptr, *ae = nullptr;
  if (!array_span(items, lh_e, &ab, &ae)) return;
  const char* p = ab + 1;
  while (p < ae - 1 && st.n_host < kMaxHostLanes) {
    p = skip_ws(p, ae);
    if (p >= ae - 1 || *p == ']') break;
    if (*p != '{') break;
    const char *ob = nullptr, *oe = nullptr;
    if (!object_span(p, ae, &ob, &oe)) break;
    double conf = 0, avail = 2, x0 = 0, x1 = 0, c0 = 0, c1 = 0, c2 = 0, c3 = 0, side = 0, lmt = 1;
    get_number(ob, oe, "m_LH_Confidence", &conf);
    const bool has_av = get_number(ob, oe, "m_LH_Availability_State", &avail);
    get_number(ob, oe, "m_LH_First_VR_Start", &x0);
    get_number(ob, oe, "m_LH_First_VR_End", &x1);
    get_number(ob, oe, "m_LH_Line_First_C0", &c0);
    get_number(ob, oe, "m_LH_Line_First_C1", &c1);
    get_number(ob, oe, "m_LH_Line_First_C2", &c2);
    get_number(ob, oe, "m_LH_Line_First_C3", &c3);
    get_number(ob, oe, "m_LH_Side", &side);
    get_number(ob, oe, "m_LH_Lanemark_Type", &lmt);
    if (lane_ok(static_cast<float>(conf), static_cast<int>(avail), has_av) &&
        x1 > x0 + 0.25) {
      HostLanePoly poly;
      poly.side = static_cast<int>(side);
      poly.c0 = static_cast<float>(c0);
      poly.c1 = static_cast<float>(c1);
      poly.c2 = static_cast<float>(c2);
      poly.c3 = static_cast<float>(c3);
      poly.x0 = static_cast<float>(x0);
      poly.x1 = std::min(static_cast<float>(x1), kDBevM);
      poly.lanemark_type = static_cast<int>(lmt);
      st.host_lanes[st.n_host++] = poly;
    }
    p = oe;
    p = skip_ws(p, ae);
    if (p < ae && *p == ',') ++p;
  }
  st.has_perc_lanes = st.n_host >= 1;
}

void apply_adj_lines(LiveBevState& st, const char* la_b, const char* la_e) {
  st.n_adj = 0;
  const char* items = find_key(la_b, la_e, "m_adj_line");
  if (!items || *items != '[') return;
  const char *ab = nullptr, *ae = nullptr;
  if (!array_span(items, la_e, &ab, &ae)) return;
  const char* p = ab + 1;
  while (p < ae - 1 && st.n_adj < kMaxAdjLanes) {
    p = skip_ws(p, ae);
    if (p >= ae - 1 || *p == ']') break;
    if (*p != '{') break;
    const char *ob = nullptr, *oe = nullptr;
    if (!object_span(p, ae, &ob, &oe)) break;
    double conf = 0, avail = 2, x0 = 0, x1 = 0, c0 = 0, c1 = 0, c2 = 0, c3 = 0, side = 0, lmt = 2;
    get_number(ob, oe, "m_LA_Confidence", &conf);
    const bool has_av = get_number(ob, oe, "m_LA_Availability_State", &avail);
    get_number(ob, oe, "m_LA_View_Range_Start", &x0);
    get_number(ob, oe, "m_LA_View_Range_End", &x1);
    get_number(ob, oe, "m_LA_Line_C0", &c0);
    get_number(ob, oe, "m_LA_Line_C1", &c1);
    get_number(ob, oe, "m_LA_Line_C2", &c2);
    get_number(ob, oe, "m_LA_Line_C3", &c3);
    get_number(ob, oe, "m_LA_Line_Side", &side);
    get_number(ob, oe, "m_LA_Lanemark_Type", &lmt);
    if (lane_ok(static_cast<float>(conf), static_cast<int>(avail), has_av) &&
        x1 > x0 + 0.25) {
      AdjLanePoly poly;
      poly.side = static_cast<int>(side);
      poly.c0 = static_cast<float>(c0);
      poly.c1 = static_cast<float>(c1);
      poly.c2 = static_cast<float>(c2);
      poly.c3 = static_cast<float>(c3);
      poly.x0 = static_cast<float>(x0);
      poly.x1 = std::min(static_cast<float>(x1), kDBevM);
      poly.lanemark_type = static_cast<int>(lmt);
      st.adj_lanes[st.n_adj++] = poly;
    }
    p = oe;
    p = skip_ws(p, ae);
    if (p < ae && *p == ',') ++p;
  }
}

void apply_dyn(LiveBevState& st, const char* dyn_b, const char* dyn_e) {
  double cipv = 0;
  get_number(dyn_b, dyn_e, "m_OBJ_VD_CIPV_ID", &cipv);
  st.cipv_id = static_cast<int>(cipv);
  st.n_obj = 0;
  const char* items = find_key(dyn_b, dyn_e, "m_Obj_item");
  if (!items || *items != '[') {
    st.has_perc_lead = false;
    return;
  }
  const char *ab = nullptr, *ae = nullptr;
  if (!array_span(items, dyn_e, &ab, &ae)) return;
  const char* p = ab + 1;
  while (p < ae - 1 && st.n_obj < kMaxDynObj) {
    p = skip_ws(p, ae);
    if (p >= ae - 1 || *p == ']') break;
    if (*p != '{') break;
    const char *ob = nullptr, *oe = nullptr;
    if (!object_span(p, ae, &ob, &oe)) break;
    double oid = 0, dist = 0, lat = 0, cls = 0, len = 0, wid = 0, hdg = 0;
    get_number(ob, oe, "m_OBJ_ID", &oid);
    get_number(ob, oe, "m_OBJ_Long_Distance", &dist);
    get_number(ob, oe, "m_OBJ_Lat_Distance", &lat);
    get_number(ob, oe, "m_OBJ_Object_Class", &cls);
    get_number(ob, oe, "m_OBJ_Length", &len);
    get_number(ob, oe, "m_OBJ_Width", &wid);
    get_number(ob, oe, "m_OBJ_Heading", &hdg);
    const int id = static_cast<int>(oid);
    if (id > 0 && dist > 0.5 && dist <= kDBevM) {
      BevDynObj o;
      o.obj_id = id;
      o.x_m = static_cast<float>(dist);
      o.y_m = static_cast<float>(lat);
      o.is_cipv = (st.cipv_id != 0 && id == st.cipv_id);
      o.obj_class = static_cast<int>(cls);
      o.length_m = len > 0.5 ? static_cast<float>(len) : 4.5f;
      o.width_m = wid > 0.5 ? static_cast<float>(wid) : 1.8f;
      o.heading_rad = static_cast<float>(hdg);
      st.perc_objects[st.n_obj++] = o;
    }
    p = oe;
    p = skip_ws(p, ae);
    if (p < ae && *p == ',') ++p;
  }
  st.has_perc_lead = false;
  st.lead_dist_m = 0;
  st.cipo_x_m = 0;
  st.cipo_y_m = 0;
  if (st.cipv_id != 0) {
    for (int i = 0; i < st.n_obj; ++i) {
      if (st.perc_objects[i].is_cipv) {
        st.has_perc_lead = true;
        st.lead_dist_m = st.perc_objects[i].x_m;
        st.cipo_x_m = st.perc_objects[i].x_m;
        st.cipo_y_m = st.perc_objects[i].y_m;
        break;
      }
    }
  }
}

void apply_perc(LiveBevState& st, const char* b, const char* e) {
  const char* lh = find_key(b, e, "Perception_LH_Out");
  if (lh && *lh == '{') {
    const char *ob = nullptr, *oe = nullptr;
    if (object_span(lh, e, &ob, &oe)) apply_host_lines(st, ob, oe);
  } else {
    st.n_host = 0;
    st.has_perc_lanes = false;
  }
  const char* la = find_key(b, e, "Perception_LA_Out");
  if (la && *la == '{') {
    const char *ob = nullptr, *oe = nullptr;
    if (object_span(la, e, &ob, &oe)) apply_adj_lines(st, ob, oe);
  } else {
    st.n_adj = 0;
  }
  const char* dyn = find_key(b, e, "Perception_DYN_OBJ_Out");
  if (dyn && *dyn == '{') {
    const char *ob = nullptr, *oe = nullptr;
    if (object_span(dyn, e, &ob, &oe)) apply_dyn(st, ob, oe);
  }
}

bool topic_is(std::string_view topic, const char* leaf) {
  if (topic == leaf) return true;
  const std::string pref = std::string("/gf/") + leaf;
  if (topic == pref) return true;
  return topic.size() >= std::strlen(leaf) &&
         topic.compare(topic.size() - std::strlen(leaf), std::strlen(leaf), leaf) == 0;
}

}  // namespace

bool apply_ndjson_row(LiveBevState& st, std::string_view line) {
  if (line.empty()) return false;
  const char* b = line.data();
  const char* e = line.data() + line.size();
  b = skip_ws(b, e);
  if (b >= e || *b != '{') return false;

  std::string topic;
  if (!get_string_leaf(b, e, "topic", &topic)) return false;

  double t_ns = 0;
  if (get_number(b, e, "t_ns", &t_ns) && t_ns > 0) {
    st.t_ns = static_cast<std::uint64_t>(t_ns);
  }

  const char* data_v = find_key(b, e, "data");
  const char *db = b, *de = e;
  if (data_v && *data_v == '{') {
    if (!object_span(data_v, e, &db, &de)) return false;
  }

  if (topic_is(topic, "EgoMotion")) {
    apply_ego(st, db, de);
    return true;
  }
  if (topic_is(topic, "Trajectory")) {
    apply_traj(st, db, de);
    return true;
  }
  if (topic.find("Perception_MESSAGE_Out") != std::string::npos ||
      topic_is(topic, "Perception_MESSAGE_Out_St")) {
    apply_perc(st, db, de);
    return true;
  }
  if (topic.find("UssZones") != std::string::npos) {
    double x = 0;
    if (get_number(db, de, "nearest_cm", &x)) st.nearest_cm = static_cast<float>(x);
    return true;
  }
  return false;
}

}  // namespace gf_foxglove
