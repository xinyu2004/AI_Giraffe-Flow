% Committed S then new-host. 1:1 lc_path.hpp.
% Planning only. Enter snapshots L,W. DR (x,y,ψ) from v,δ.
% Road pose (gf_lc_pose): paint when geom; DR increment only while paint gone.
% Remap = FCM host jumped (pose). Reg = law switch, only in the new band.
% Before reg: S-curve, s monotonic, hold_ok + land_ok can abort.
% After reg: same host-keep as idle; path = m_lat_traj (not y=e·t). No abort.
% Done is dwell bookkeeping, not a law switch. Cool is m_plan. AFC never calls.

function [x_m, y_m, horizon_m, hold] = m_lc_path(lc_side, v, d_f, d_r, rel_r, dt, ...
                                                 steer_deg, d_hard, rel_f, hdg_f, ...
                                                 e_y, c1, paint_ok, c2, c3, land_ok)
  persistent st
  p = gf_plan_cal();
  if isempty(st)
    st = lc_path_zero();
  end
  if nargin < 2
    v = 0.0;
  end
  if nargin < 3
    d_f = 0.0;
  end
  if nargin < 4
    d_r = 0.0;
  end
  if nargin < 5
    rel_r = 0.0;
  end
  if nargin < 6 || isempty(dt) || dt <= 0.0
    dt = p.plan_dt_s;
  end
  if nargin < 7 || isempty(steer_deg)
    steer_deg = 0.0;
  end
  if nargin < 8 || isempty(d_hard)
    d_hard = 1.0e6;
  end
  if nargin < 9 || isempty(rel_f)
    rel_f = 0.0;
  end
  if nargin < 10 || isempty(hdg_f)
    hdg_f = 0.0;
  end
  if nargin < 11 || isempty(e_y)
    e_y = 0.0;
  end
  if nargin < 12 || isempty(c1)
    c1 = 0.0;
  end
  if nargin < 13 || isempty(paint_ok)
    paint_ok = 0.0;
  end
  if nargin < 14 || isempty(c2)
    c2 = 0.0;
  end
  if nargin < 15 || isempty(c3)
    c3 = 0.0;
  end
  if nargin < 16 || isempty(land_ok)
    land_ok = 1.0;
  end
  dt = gf_clamp(dt, p.lc_dt_min_s, p.lc_dt_max_s);
  v = max(0.0, v);
  side = 0;
  if lc_side > 0.5
    side = 1;
  elseif lc_side < -0.5
    side = -1;
  end

  hold = hold_from_st(st);
  N = p.traj_n;
  x_m = zeros(1, N);
  y_m = zeros(1, N);
  horizon_m = 0.0;

  if side == 0
    st = lc_path_zero();
    return
  end
  if st.active > 0.5
    side = st.side;
  end

  if st.active == 0
    L = gf_lc_L_need();
    if ~gf_lc_can(1, d_f, d_r, rel_r, v, 0.0, d_hard, rel_f, hdg_f)
      return
    end
    st.active = 1;
    st.side = side;
    st.L = L;
    st.W = side * p.lane_width_m;
    st.s = 0.0;
    st.x = 0.0;
    st.y = 0.0;
    st.psi = 0.0;
    st.plant_n = 0;
    st.reg = 0;
    st.reg_d = 0.0;
    st.pose = gf_lc_pose([]);
  end

  st = lc_dead_reckon(st, v, dt, steer_deg, p.wheelbase_m);
  if ~isfield(st, 'pose')
    st.pose = gf_lc_pose([]);
  end
  if ~isfield(st, 'plant_n')
    st.plant_n = 0;
  end
  if ~isfield(st, 'reg')
    st.reg = 0;
    st.reg_d = 0.0;
  end
  st.pose = gf_lc_pose(st.pose, e_y, c1, paint_ok, st.W, st.y, st.psi);
  y_use = st.pose.y;
  psi_use = st.pose.psi;
  if st.reg < 0.5
    if land_ok < 0.5 || ~gf_lc_hold_ok(d_f, d_r, rel_r, v, d_hard, rel_f, hdg_f)
      hold = abort_hold(st);
      st = lc_path_zero();
      return
    end
  end
  [ylo, yhi] = lc_corridor(st.W, p.lane_width_m);
  if st.reg > 0.5
    s_raw = st.s;
  else
    s_raw = lc_progress_s(st.x, y_use, st.L, st.W, p.lane_width_m);
  end
  st.s = max(st.s, s_raw);
  [psi_s, k_s, d_s] = lc_geom(st.s, st.L, st.W, p.wheelbase_m);
  if st.reg < 0.5 && st.pose.remapped > 0.5
    in_band = abs(e_y) < p.lc_settle_ey_m;
    if ~in_band && st.s + 1.0e-3 >= st.L
      in_band = lc_in_target(y_use, st.W, p.lane_width_m, ylo, yhi);
    end
    if in_band
      st.reg_d = d_s;
      st.reg = 1;
    end
  end
  if st.reg > 0.5
    if paint_ok > 0.5
      d_s = gf_lat_host_delta(1, e_y, c1, c2, c3, v);
    else
      d_s = st.reg_d;
    end
    d_s = lc_delta_in_band(d_s, y_use, st.W, p.lane_width_m, ylo, yhi, 1);
    st.reg_d = d_s;
    psi_s = 0.0;
    k_s = 0.0;
    y_s = st.W;
    hold.e = e_y;
    hold.epsi = psi_use;
  else
    d_s = lc_delta_in_band(d_s, y_use, st.W, p.lane_width_m, ylo, yhi, 0);
    y_s = gf_clamp(st.W * lc_sigma(st.s / max(st.L, 1.0e-3)), ylo, yhi);
    dx = st.x - st.s;
    dy = y_use - y_s;
    hold.e = -dx * sin(psi_s) + dy * cos(psi_s);
    hold.epsi = psi_use - psi_s;
  end
  hold.s_done = st.s;
  hold.L = st.L;
  hold.side = st.side;
  hold.psi = psi_s;
  hold.kappa = k_s;
  hold.delta_ff = d_s;
  hold.y = st.y;
  hold.y_s = y_s;
  hold.y_road = y_use;
  hold.remapped = st.pose.remapped;
  hold.paint_ok = st.pose.paint_ok;
  hold.reg = st.reg;
  psi_lim = p.lc_settle_steer_deg * pi / 180.0;
  in_tgt = 0;
  psi_done = st.psi;
  if paint_ok > 0.5
    psi_done = psi_use;
    if st.pose.remapped > 0.5
      in_tgt = abs(e_y) < p.lc_settle_ey_m;
    else
      in_tgt = lc_in_target(y_use, st.W, p.lane_width_m, ylo, yhi);
    end
  else
    in_tgt = lc_in_target(st.y, st.W, p.lane_width_m, ylo, yhi);
  end
  d_deg = d_s * 180.0 / pi;
  d_lim = abs(d_deg) < p.lc_settle_steer_deg;
  trk_lim = abs(steer_deg - d_deg) < p.lc_settle_steer_deg;
  planted = in_tgt && abs(psi_done) < psi_lim ...
            && abs(steer_deg) < p.lc_settle_steer_deg && d_lim && trk_lim;
  if planted
    st.plant_n = st.plant_n + 1;
  else
    st.plant_n = 0;
  end
  hold.plant_n = st.plant_n;
  if planted && st.plant_n >= p.lc_done_hold_n
    hold.done = 1;
    hold.active = 0;
    st = lc_path_zero();
    return
  end

  hold.active = 1;
  if st.reg > 0.5
    D = max(p.traj_horizon_floor_m, v * 2.0);
    T = D / max(v, p.traj_speed_floor_mps);
    [x_m, y_m, horizon_m] = m_lat_traj(v, D, T, 1, e_y, c1, c2, c3, 1.0e6);
    return
  end
  remain = max(0.0, st.L - st.s);
  horizon_m = remain;
  x_m(1) = 0.0;
  y_m(1) = 0.0;
  ds = remain / max(N - 1, 1);
  c0 = cos(psi_use);
  s0 = sin(psi_use);
  for i = 2:N
    t = st.s + ds * (i - 1);
    xs = t;
    ys = gf_clamp(st.W * lc_sigma(t / max(st.L, 1.0e-3)), ylo, yhi);
    rx = xs - st.x;
    ry = ys - y_use;
    x_m(i) = rx * c0 + ry * s0;
    y_m(i) = -rx * s0 + ry * c0;
  end
end

function z = lc_path_zero()
  z.active = 0;
  z.side = 0;
  z.L = 0.0;
  z.W = 0.0;
  z.s = 0.0;
  z.x = 0.0;
  z.y = 0.0;
  z.psi = 0.0;
  z.plant_n = 0;
  z.reg = 0;
  z.reg_d = 0.0;
  z.pose = gf_lc_pose([]);
end

function hold = hold_from_st(st)
  hold = struct('active', 0, 'done', 0, 'aborted', 0, ...
                's_done', st.s, 'L', st.L, 'side', st.side, ...
                'delta_ff', 0.0, 'psi', 0.0, 'kappa', 0.0, ...
                'e', 0.0, 'epsi', 0.0, 'y', 0.0, 'y_s', 0.0, ...
                'y_road', 0.0, 'remapped', 0, 'paint_ok', 0, ...
                'reg', 0, 'plant_n', 0);
end

function hold = abort_hold(st)
  hold = hold_from_st(st);
  hold.aborted = 1;
  hold.active = 0;
end

function st = lc_dead_reckon(st, v, dt, steer_deg, wb)
  wb = max(wb, 0.5);
  delta = steer_deg * pi / 180.0;
  kap = -tan(delta) / wb;
  st.psi = st.psi + v * kap * dt;
  st.x = st.x + v * cos(st.psi) * dt;
  st.y = st.y + v * sin(st.psi) * dt;
end

function sig = lc_sigma(u)
  u = min(1.0, max(0.0, u));
  sig = 10.0 * u^3 - 15.0 * u^4 + 6.0 * u^5;
end

function u = lc_sigma_inv(s)
  s = min(1.0, max(0.0, s));
  lo = 0.0;
  hi = 1.0;
  for k = 1:20
    mid = 0.5 * (lo + hi);
    if lc_sigma(mid) < s
      lo = mid;
    else
      hi = mid;
    end
  end
  u = 0.5 * (lo + hi);
end

function [ylo, yhi] = lc_corridor(W, lw)
  half = 0.5 * max(lw, 1.0);
  if W >= 0.0
    ylo = -half;
    yhi = W + half;
  else
    yhi = half;
    ylo = W - half;
  end
end

function ok = lc_in_target(y, W, lw, ylo, yhi)
  pad = 0.30;
  line = 0.5 * max(lw, 1.0);
  if W >= 0.0
    ok = (y >= line - 0.20) && (y <= yhi - pad);
  else
    ok = (y <= -line + 0.20) && (y >= ylo + pad);
  end
end

function d = lc_delta_in_band(d_s, y, W, lw, ylo, yhi, across)
  if nargin < 7
    across = 0;
  end
  pad = 0.30;
  line = 0.5 * max(lw, 1.0);
  d = d_s;
  if across < 0.5
    if W >= 0.0
      if y < line + pad
        d = min(d, 0.0);
      end
    else
      if y > -line - pad
        d = max(d, 0.0);
      end
    end
  end
  if y > yhi - pad
    d = max(d, 0.04 * (y - (yhi - pad)));
  elseif y < ylo + pad
    d = min(d, -0.04 * ((ylo + pad) - y));
  end
end

function s = lc_progress_s(x, y, L, W, lw)
  L = max(L, 1.0e-3);
  u_x = min(1.0, max(0.0, x / L));
  if abs(W) < 1.0e-3
    s = min(max(0.0, x), L);
    return
  end
  lat = y / W;
  if lat < 0.0
    lat = 0.0;
  end
  if lat > 1.0
    lat = 1.0;
  end
  u_y = lc_sigma_inv(lat);
  u_rise = 0.25;
  line = 0.5 * max(lw, 1.0);
  if abs(y) < line + 0.30
    u = min([u_x, max(u_rise, u_y), 0.5]);
  elseif u_y < 0.5
    u = min(u_x, max(u_rise, u_y));
  else
    u = min(u_x, u_y);
  end
  s = u * L;
end

function [psi, kappa, delta] = lc_geom(s, L, W, wb)
  L = max(L, 1.0e-3);
  u = min(1.0, max(0.0, s / L));
  sigp = 30.0 * u^2 * (1.0 - u)^2;
  sigpp = 60.0 * u * (1.0 - u) * (1.0 - 2.0 * u);
  yp = (W / L) * sigp;
  ypp = (W / (L * L)) * sigpp;
  psi = atan(yp);
  kappa = ypp / ((1.0 + yp * yp)^1.5);
  delta = -atan(wb * kappa);
end
