% AFC Host entry — one call per tick. Plan then control; no mixed laws.
% Plan always emits δ_ff (S or host-keep). Ctrl only follows.
% AFC keeps lc_side=0 (host LKA). plus may pass LC + land motion.

function out = m_plan_tick(v, steer_deg, lane_valid, e_y, c0, c1, c2, c3, x_end, ...
                           lane_conf, lane_count, obj, D_see_prev, T_plan_prev, ...
                           v_sign_max, v_sign_min, lc_side, d_f, d_r, rel_r, dt, d_hard, ...
                           rel_f, hdg_f, paint_ok, land_ok)
  t0 = tic;
  p = gf_plan_cal();
  if nargin < 10
    lane_conf = 1.0;
  end
  if nargin < 11
    lane_count = 1.0;
  end
  if nargin < 12
    obj = [];
  end
  if nargin < 13
    D_see_prev = 0.0;
  end
  if nargin < 14
    T_plan_prev = 0.0;
  end
  if nargin < 15 || isempty(v_sign_max)
    v_sign_max = 1.0e6;
  end
  if nargin < 16 || isempty(v_sign_min)
    v_sign_min = 0.0;
  end
  if nargin < 17 || isempty(lc_side)
    lc_side = 0;
  end
  if nargin < 18 || isempty(d_f)
    d_f = 0.0;
  end
  if nargin < 19 || isempty(d_r)
    d_r = 0.0;
  end
  if nargin < 20 || isempty(rel_r)
    rel_r = 0.0;
  end
  if nargin < 21 || isempty(dt) || dt <= 0.0
    dt = p.plan_dt_s;
  end
  if nargin < 22 || isempty(d_hard)
    d_hard = 1.0e6;
  end
  if nargin < 23 || isempty(rel_f)
    rel_f = 0.0;
  end
  if nargin < 24 || isempty(hdg_f)
    hdg_f = 0.0;
  end
  if nargin < 25 || isempty(paint_ok)
    paint_ok = 0.0;
  end
  if nargin < 26 || isempty(land_ok)
    land_ok = 1.0;
  end

  plan = m_plan(v, steer_deg, lane_valid, e_y, c0, c1, c2, c3, x_end, ...
                obj, D_see_prev, T_plan_prev, v_sign_max, v_sign_min, ...
                lc_side, d_f, d_r, rel_r, dt, d_hard, rel_f, hdg_f, paint_ok, land_ok);
  ctrl = m_ctrl(plan, v, steer_deg, lane_valid, e_y, c1);

  out.throttle = ctrl.throttle;
  out.brake = ctrl.brake;
  out.steer = ctrl.steer;
  out.mode = ctrl.mode;
  out.target_speed_mps = ctrl.target_speed_mps;
  out.D_see = plan.D_see;
  out.T_plan = plan.T_plan;
  out.D_occ = plan.D_occ;
  out.a_req = plan.a_req;
  out.horizon_m = plan.horizon_m;
  out.s_stop = plan.s_stop;
  out.x_m = plan.x_m;
  out.y_m = plan.y_m;
  out.v_mps = plan.v_mps;
  out.allow_lc = plan.allow_lc;
  out.lc_s_done = plan.lc_s_done;
  out.lc_L = plan.lc_L;
  out.delta_ff = plan.delta_ff;
  out.psi = plan.psi;
  out.target = plan.target;
  out.err_delta = ctrl.err_delta;
  out.err_v = ctrl.err_v;
  out.err_e = ctrl.err_e;
  out.err_epsi = ctrl.err_epsi;
  out.y_dr = plan.y_dr;
  out.y_s = plan.y_s;
  out.y_road = 0.0;
  out.remapped = 0;
  out.paint_ok = 0;
  if isfield(plan, 'y_road')
    out.y_road = plan.y_road;
  end
  if isfield(plan, 'remapped')
    out.remapped = plan.remapped;
  end
  if isfield(plan, 'paint_ok')
    out.paint_ok = plan.paint_ok;
  end
  out.commit_m = 0.0;
  out.reg = 0;
  out.plant_n = 0;
  if isfield(plan, 'commit_m')
    out.commit_m = plan.commit_m;
  end
  if isfield(plan, 'reg')
    out.reg = plan.reg;
  end
  if isfield(plan, 'plant_n')
    out.plant_n = plan.plant_n;
  end
  out.t_m_s = toc(t0);
end
