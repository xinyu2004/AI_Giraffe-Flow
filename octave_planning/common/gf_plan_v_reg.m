% Comfort / late speed at s to be stopped at s_stop. Plan only; not AEB.
% Inactive line (cap) → 1e6 so min() is a no-op.
% Within hold of the line → 0. Kinematics only — do NOT use acc_time_gap (follow).
function vi = gf_plan_v_reg(s, s_stop, v_ego)
  p = gf_plan_cal();
  vi = 1.0e6;
  if nargin < 3 || isempty(v_ego)
    v_ego = 0.0;
  end
  if nargin < 2 || isempty(s_stop) || s_stop <= 0.0 || s_stop >= (p.d_cal_cap_m - 0.5)
    return;
  end
  hold = max(p.reg_stop_hold_m, 0.2);
  gap = s_stop - s;
  if gap <= hold
    vi = 0.0;
    return;
  end
  a = max(p.reg_stop_decel_mps2, 0.5);
  s_need = (max(v_ego, 0.0) * max(v_ego, 0.0)) / (2.0 * a) + hold;
  if gap < s_need
    a = max(p.reg_stop_late_mps2, a);
  end
  vi = sqrt(max(0.0, 2.0 * a * (gap - hold)));
end
