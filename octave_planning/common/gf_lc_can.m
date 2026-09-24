% Layer: neighbor land + leave-host. 1:1 lc_side.hpp gf_lc_can / gf_lc_host_ok.
% Time domain: occupy T=L/v, then front/rear/hard conflict time. Not a metre stick.
% Front rel<0 closes. Rear rel>0 closes. Heading: same-way or veto. AFC never calls.

function ok = gf_lc_can(have, d_f, d_r, rel_r, v, D_see, d_hard, rel_f, hdg_f)
  ok = 0;
  if ~have
    return
  end
  if nargin < 7 || isempty(d_hard)
    d_hard = 1.0e6;
  end
  if nargin < 8 || isempty(rel_f)
    rel_f = 0.0;
  end
  if nargin < 9 || isempty(hdg_f)
    hdg_f = 0.0;
  end
  T = gf_lc_T_need(v);
  if T > gf_plan_cal().t_lc_min_s
    return
  end
  if d_f < 100.0 && ~gf_lc_same_way(hdg_f)
    return
  end
  if ~gf_lc_time_ok(d_f, max(0.0, -rel_f), rel_f > 0.3, v, T)
    return
  end
  if ~gf_lc_time_ok(d_r, max(0.0, rel_r), rel_r < -0.3, v, T)
    return
  end
  if ~gf_lc_time_ok(d_hard, max(0.0, v), 0, v, T)
    return
  end
  if D_see < 0.0
    return
  end
  ok = 1;
end

function L = gf_lc_L_need()
  p = gf_plan_cal();
  L = p.d_lc_min_m;
end

function T = gf_lc_T_need(v)
  p = gf_plan_cal();
  T = gf_lc_L_need() / max(v, p.traj_speed_floor_mps);
end

function t = gf_lc_t_need(v)
  t = gf_lc_T_need(v);
end

function ok = gf_lc_same_way(hdg)
  p = gf_plan_cal();
  ok = abs(hdg) <= p.lc_hdg_same;
end

function ok = gf_lc_time_ok(d, close_mps, opening, v, T)
  p = gf_plan_cal();
  ok = 0;
  if d < p.d_lc_rear_min_m
    return
  end
  if close_mps > p.closing_min_mps
    ttc = d / max(close_mps, 0.05);
    if ttc < T + p.lc_ttc_margin_s
      return
    end
  elseif opening == 0
    if d + 0.5 < max(p.acc_gap_min_m, max(0.0, v) * p.acc_time_gap_s)
      return
    end
  end
  ok = 1;
end

function ok = gf_lc_rear_ok(d_r, rel_r, v)
  T = gf_lc_T_need(v);
  if T > gf_plan_cal().t_lc_min_s
    ok = 0;
    return
  end
  ok = gf_lc_time_ok(d_r, max(0.0, rel_r), rel_r < -0.3, v, T);
end

function ok = gf_lc_host_ok(d_f, rel_f, hdg_f, v, d_hard)
  % Leave-host gate. Same time_ok; same-speed host lead is overtake, not veto.
  % Opening=1 skips ACC time-gap. Host bumper / closing TTC / hard still apply.
  ok = 0;
  if nargin < 3 || isempty(hdg_f)
    hdg_f = 0.0;
  end
  if nargin < 4
    v = 0.0;
  end
  if nargin < 5 || isempty(d_hard)
    d_hard = 1.0e6;
  end
  if nargin < 2 || isempty(rel_f)
    rel_f = 0.0;
  end
  p = gf_plan_cal();
  if d_f < p.d_lc_host_min_m
    return
  end
  T = gf_lc_T_need(v);
  if d_f < 100.0 && ~gf_lc_same_way(hdg_f)
    return
  end
  if ~gf_lc_time_ok(d_f, max(0.0, -rel_f), 1, v, T)
    return
  end
  if ~gf_lc_time_ok(d_hard, max(0.0, v), 0, v, T)
    return
  end
  ok = 1;
end

function ok = gf_lc_hold_ok(d_f, d_r, rel_r, v, d_hard, rel_f, hdg_f)
  % Hold abort: world conflict only. T>t_lc_min is enter, not here.
  ok = 0;
  if nargin < 5 || isempty(d_hard)
    d_hard = 1.0e6;
  end
  if nargin < 6 || isempty(rel_f)
    rel_f = 0.0;
  end
  if nargin < 7 || isempty(hdg_f)
    hdg_f = 0.0;
  end
  T = gf_lc_T_need(v);
  if d_f < 100.0 && ~gf_lc_same_way(hdg_f)
    return
  end
  if ~gf_lc_time_ok(d_f, max(0.0, -rel_f), rel_f > 0.3, v, T)
    return
  end
  if ~gf_lc_time_ok(d_r, max(0.0, rel_r), rel_r < -0.3, v, T)
    return
  end
  if ~gf_lc_time_ok(d_hard, max(0.0, v), 0, v, T)
    return
  end
  ok = 1;
end
