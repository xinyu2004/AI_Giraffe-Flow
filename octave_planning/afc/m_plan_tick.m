% AFC Host entry — one call per tick.
% Scene: D_see (marks/occupy/optics) + stop-line from TSR + occupy targets.
% Plan: path in D_see; v(s) = min(vis, sign max, comfort line, peers, follow)
%       + optional sign-min floor when no stop-line.
% Exec: gf_lon_exec tracks v_plan(0); a_req occupy + late/at-line light.

function out = m_plan_tick(v, steer_deg, lane_valid, e_y, c0, c1, c2, c3, x_end, ...
                           lane_conf, lane_count, obj, D_see_prev, T_plan_prev, ...
                           v_sign_max, v_sign_min)
  t0 = tic;
  p = gf_plan_cal();
  v = max(0.0, v);
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

  D_occ = gf_plan_occlusion(obj, c0);
  D_fov = gf_plan_d_fov(c0, c1, c2, c3, x_end);
  [D_see, T_plan] = gf_plan_horizon(v, lane_valid, e_y, c1, x_end, ...
                                   D_occ, D_fov, D_see_prev, T_plan_prev);

  lane_ok = gf_lane_usable(lane_valid, e_y, c1);
  if abs(e_y) > p.lat_ey_slow_m
    lane_ok = 0;
  end

  [x_m, y_m, horizon_m] = m_lat_traj(v, D_see, T_plan, lane_valid, ...
                                    c0, c1, c2, c3, x_end);
  s_stop = gf_plan_reg_stop(obj, c0);
  v_s = gf_plan_speed_profile(x_m, v, obj, D_see, lane_ok, c0, s_stop, ...
                              v_sign_max, v_sign_min);
  if isempty(v_s)
    v_plan = 0.0;
  else
    v_plan = v_s(1);
  end
  a_req = gf_lon_a_req_n(v, obj, c0);
  if D_see < p.d_vis_tight_m
    a_max = max(p.aeb_decel_mps2, 0.5);
    a_req = min(a_max, a_req * p.a_req_vis_gain);
  end
  a_reg = gf_lon_a_req_stop(v, s_stop);
  if a_reg > a_req
    a_req = a_reg;
  end
  if ~lane_ok
    v_plan = 0.0;
    v_s = zeros(size(x_m));
  end
  ctrl = gf_lon_exec(v, v_plan, a_req);
  steer = m_lat_lka(lane_valid, e_y, c1, steer_deg);

  allow_lc = 0.0;
  % Demoted: no real corridor product yet (adj count ≠ LC). Keep flag 0.

  out.throttle = ctrl.throttle;
  out.brake = ctrl.brake;
  out.steer = steer;
  out.mode = ctrl.mode;
  out.target_speed_mps = ctrl.target_speed_mps;
  out.D_see = D_see;
  out.T_plan = T_plan;
  out.D_occ = D_occ;
  out.a_req = a_req;
  out.horizon_m = horizon_m;
  out.s_stop = s_stop;
  out.x_m = x_m;
  out.y_m = y_m;
  out.v_mps = v_s;
  out.allow_lc = allow_lc;
  out.t_m_s = toc(t0);
end
