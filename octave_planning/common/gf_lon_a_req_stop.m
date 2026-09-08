% Late / at-line brake for a known red/yellow. Comfort-enough → 0 (v_reg only).
% Not occupy AEB (cap is reg_stop_late, not aeb_decel).
% Inside hold: request late brake so exec does not thr-hold crawl.
function a_req = gf_lon_a_req_stop(v, s_stop)
  p = gf_plan_cal();
  a_req = 0.0;
  if nargin < 2 || isempty(s_stop) || s_stop <= 0.0 || s_stop >= (p.d_cal_cap_m - 0.5)
    return;
  end
  hold = max(p.reg_stop_hold_m, 0.2);
  a_c = max(p.reg_stop_decel_mps2, 0.5);
  a_late = max(p.reg_stop_late_mps2, a_c);
  vv = max(0.0, v);
  if s_stop <= hold
    if vv > 0.05
      a_req = a_late;
    end
    return;
  end
  s_need = (vv * vv) / (2.0 * a_c) + hold;
  if s_stop > s_need + 0.05
    return;
  end
  a_kin = (vv * vv) / (2.0 * max(s_stop - hold, 0.2));
  a_req = min(a_late, max(0.0, a_kin));
end
