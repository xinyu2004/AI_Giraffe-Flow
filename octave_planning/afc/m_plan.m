% Planning only. 1:1 plan_tick.hpp m_plan.
% Path + ψ/κ/δ + v(s) + a_req + target. No pedals, no steer.
% Follow: D_see along corridor (d_f, d_hard), not host poly.
% Hold lon skips host objs (overtake).
% Idle and post-reg: same host-keep δ (gf_lat_host_delta). Cool only blocks re-enter.
% S-corridor δ is m_lc_path before reg. Remap is pose only. AFC lc_side=0.

function plan = m_plan(v, steer_deg, lane_valid, e_y, c0, c1, c2, c3, x_end, ...
                       obj, D_see_prev, T_plan_prev, v_sign_max, v_sign_min, ...
                       lc_side, d_f, d_r, rel_r, dt, d_hard, rel_f, hdg_f, paint_ok, land_ok)
  persistent cool
  p = gf_plan_cal();
  v = max(0.0, v);
  if nargin < 11
    D_see_prev = 0.0;
  end
  if nargin < 12
    T_plan_prev = 0.0;
  end
  if nargin < 13 || isempty(v_sign_max)
    v_sign_max = 1.0e6;
  end
  if nargin < 14 || isempty(v_sign_min)
    v_sign_min = 0.0;
  end
  if nargin < 15 || isempty(lc_side)
    lc_side = 0;
  end
  if nargin < 16 || isempty(d_f)
    d_f = 0.0;
  end
  if nargin < 17 || isempty(d_r)
    d_r = 0.0;
  end
  if nargin < 18 || isempty(rel_r)
    rel_r = 0.0;
  end
  if nargin < 19 || isempty(dt) || dt <= 0.0
    dt = p.plan_dt_s;
  end
  if nargin < 20 || isempty(d_hard)
    d_hard = 1.0e6;
  end
  if nargin < 21 || isempty(rel_f)
    rel_f = 0.0;
  end
  if nargin < 22 || isempty(hdg_f)
    hdg_f = 0.0;
  end
  if nargin < 23 || isempty(paint_ok)
    paint_ok = 0.0;
  end
  if nargin < 24 || isempty(land_ok)
    land_ok = 1.0;
  end
  if isempty(cool)
    cool = 0;
  end

  D_occ = gf_plan_occlusion(obj, c0);
  D_fov = gf_plan_d_fov(c0, c1, c2, c3, x_end);
  [D_see_h, T_plan_h] = gf_plan_horizon(v, lane_valid, e_y, c1, x_end, ...
                                       D_occ, D_fov, D_see_prev, T_plan_prev);

  side_in = lc_side;
  if cool > 0.5
    side_in = 0;
  end
  [x_m, y_m, horizon_m, hold] = m_lc_path(side_in, v, d_f, d_r, rel_r, dt, ...
                                          steer_deg, d_hard, rel_f, hdg_f, ...
                                          e_y, c1, paint_ok, c2, c3, land_ok);
  follow = hold.active > 0.5;
  host_d = gf_lat_host_delta(lane_valid, e_y, c1, c2, c3, v);
  if follow
    D_see = min([p.d_cal_cap_m, max(d_f, 0.5), max(d_hard, 0.5)]);
    T_plan = max(p.t_plan_min_s, D_see / max(v, p.traj_speed_floor_mps));
    lane_ok = 1;
    cool = 0;
  else
    D_see = D_see_h;
    T_plan = T_plan_h;
    [x_m, y_m, horizon_m] = m_lat_traj(v, D_see, T_plan, lane_valid, ...
                                      c0, c1, c2, c3, x_end);
    lane_ok = gf_lane_usable(lane_valid, e_y, c1);
    if abs(e_y) > p.lat_ey_slow_m
      lane_ok = 0;
    end
    if hold.done > 0.5 || hold.aborted > 0.5
      cool = p.lc_cool_n;
    end
    if cool > 0.5
      cool = cool - 1;
    end
  end

  s_stop = gf_plan_reg_stop(obj, c0);
  lon_obj = obj;
  if follow
    lon_obj = [];
  end
  v_s = gf_plan_speed_profile(x_m, v, lon_obj, D_see, lane_ok, c0, s_stop, ...
                              v_sign_max, v_sign_min);
  if isempty(v_s)
    v_plan = 0.0;
  else
    v_plan = v_s(1);
  end
  a_req = gf_lon_a_req_n(v, lon_obj, c0);
  if D_see < p.d_vis_tight_m
    a_max = max(p.aeb_decel_mps2, 0.5);
    a_req = min(a_max, a_req * p.a_req_vis_gain);
  end
  a_reg = gf_lon_a_req_stop(v, s_stop);
  if a_reg > a_req
    a_req = a_reg;
  end
  if follow
    d_need = (v * v) / (2.0 * max(p.lc_a_plan_mps2, 0.5));
    if d_need > D_see
      a_s = (v * v) / (2.0 * max(D_see, 1.0));
      a_req = max(a_req, min(a_s, max(p.aeb_decel_mps2, 0.5)));
    end
  end
  if ~lane_ok
    v_plan = 0.0;
    v_s = zeros(size(x_m));
  end

  target = 0;
  if follow
    target = 1;
  end

  plan.D_see = D_see;
  plan.T_plan = T_plan;
  plan.D_occ = D_occ;
  plan.a_req = a_req;
  plan.horizon_m = horizon_m;
  plan.s_stop = s_stop;
  plan.x_m = x_m;
  plan.y_m = y_m;
  plan.v_mps = v_s;
  plan.v_plan = v_plan;
  plan.allow_lc = follow;
  plan.lc_s_done = hold.s_done;
  plan.lc_L = hold.L;
  if follow
    plan.delta_ff = hold.delta_ff;
  else
    plan.delta_ff = host_d;
  end
  plan.commit_m = 0.0;
  plan.reg = 0;
  if isfield(hold, 'reg')
    plan.reg = hold.reg;
  end
  plan.plant_n = 0;
  if isfield(hold, 'plant_n')
    plan.plant_n = hold.plant_n;
  end
  plan.e = hold.e;
  plan.epsi = hold.epsi;
  plan.y_dr = 0.0;
  plan.y_s = 0.0;
  if isfield(hold, 'y')
    plan.y_dr = hold.y;
  end
  if isfield(hold, 'y_s')
    plan.y_s = hold.y_s;
  end
  plan.y_road = 0.0;
  plan.remapped = 0;
  plan.paint_ok = 0;
  if isfield(hold, 'y_road')
    plan.y_road = hold.y_road;
  end
  if isfield(hold, 'remapped')
    plan.remapped = hold.remapped;
  end
  if isfield(hold, 'paint_ok')
    plan.paint_ok = hold.paint_ok;
  end
  plan.psi = hold.psi;
  plan.target = target;
  plan.lane_ok = lane_ok;
end
