% Follow gap floor, never inside d_stop. 1:1 lon_desired_gap().
function g = gf_lon_desired_gap(v)
  p = gf_plan_cal();
  g = max(p.acc_gap_min_m, max(0.0, v) * p.acc_time_gap_s);
  g = max(g, gf_lon_d_stop(v) + p.acc_gap_over_stop_m);
  g = min(g, p.acc_gap_max_m);
  g = max(g, gf_lon_d_stop(v) + p.acc_gap_over_stop_m);
end
