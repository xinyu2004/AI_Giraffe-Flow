% Stopping envelope scale. 1:1 lon_d_stop().
function d_stop = gf_lon_d_stop(v)
  p = gf_plan_cal();
  a = max(p.aeb_decel_mps2, 0.5);
  vv = max(0.0, v);
  d_stop = (vv * vv) / (2.0 * a) + vv * p.aeb_react_s + p.aeb_d_min_m + p.aeb_margin_m;
end
