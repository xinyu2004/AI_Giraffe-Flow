% Planned speed at station s. Take-strict min of:
%   vis cap, sign max, comfort stop-line, host-lane occupy follow, adjacent flow.
% Sign min floors cruise only when no stop-line; stop/follow may still cut.
% Light is a speed profile (v_reg); late/at-line brake is lon_a_req_stop, not occupy.
% Host follow: gap-error P on (gap - τ·v - g0), capped by kinematics (not raw (gap-g0)/τ).
% v_sign_* are NOT gf_plan_v_cap_vis (sight distance).
function vi = gf_plan_v_at_s(s, v_ego, obj, D_see, lane_ok, c0, s_stop, ...
                             v_sign_max, v_sign_min)
  p = gf_plan_cal();
  if nargin < 6 || isempty(c0)
    c0 = 0.0;
  end
  if nargin < 8 || isempty(v_sign_max)
    v_sign_max = 1.0e6;
  end
  if nargin < 9 || isempty(v_sign_min)
    v_sign_min = 0.0;
  end
  v_cap = gf_plan_v_cap_vis(D_see);
  if ~lane_ok
    vi = 0.0;
    return;
  end
  if s > D_see + 0.05
    vi = 0.0;
    return;
  end
  vi = v_cap;
  if nargin < 7 || isempty(s_stop)
    s_stop = gf_plan_reg_stop(obj, c0);
  end
  vi = min(vi, v_sign_max);
  if v_sign_min > 0.5 && s_stop >= (p.d_cal_cap_m - 0.5)
    vi = max(vi, min([v_sign_min, v_sign_max, v_cap]));
  end
  vi = min(vi, gf_plan_v_reg(s, s_stop, v_ego));
  vi = min(vi, gf_plan_v_peers(s, v_ego, obj, c0));
  [n, d, rel, lat, len_m, cls, hdg, ped] = gf_plan_obj_unpack(obj);
  if n < 1
    return;
  end
  a = max(p.aeb_decel_mps2, 0.5);
  vv = max(0.0, v_ego);
  for k = 1:n
    if d(k) > p.lon_max_d_m
      continue;
    end
    w = gf_plan_obj_weight(lat(k), hdg(k), ped(k), len_m(k), cls(k), c0, rel(k));
    if w <= 0.0
      continue;
    end
    if rel(k) > p.cutin_close_mps && w < 1.0
      continue;
    end
    gap = d(k) - s;
    if gap <= p.aeb_d_min_m
      if w > 0.5
        vi = 0.0;
      end
      continue;
    end
    v_obj = max(0.0, vv + rel(k));
    v_kin = sqrt(max(0.0, v_obj * v_obj + 2.0 * a * (gap - p.aeb_d_min_m)));
    % Gap-error follow: close when gap > τ·v+g0, open when tighter (still ≤ v_kin).
    desired = p.acc_gap_min_m + p.acc_time_gap_s * max(v_obj, 0.5);
    v_follow = v_obj + max(-4.0, min(3.0, 0.4 * (gap - desired)));
    v_lim = v_kin;
    if w >= 1.0 || rel(k) <= 0.0
      v_lim = min(v_kin, max(0.0, v_follow));
    end
    vi = min(vi, v_lim * w + v_cap * (1.0 - w));
  end
end
