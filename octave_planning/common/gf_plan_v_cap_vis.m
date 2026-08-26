% Speed cap from sight distance. 1:1 plan_v_cap_vis().
function vc = gf_plan_v_cap_vis(D_see)
  p = gf_plan_cal();
  a = max(p.aeb_decel_mps2, 0.5);
  vc = sqrt(max(0.0, 2.0 * a * max(0.0, D_see - p.aeb_d_min_m)));
  vc = min(vc, p.cruise_v_mps);
end
