% Safety decel 0..a_max. Optional w_in skips lat_weight (multi-target already weighted).
function a_req = gf_lon_a_req(v, lead_valid, d, rel, lat, w_in)
  p = gf_plan_cal();
  a_req = 0.0;
  if nargin >= 6
    w = w_in;
  else
    w = gf_plan_lat_weight(lat);
  end
  if ~lead_valid || w <= 0.0 || d > p.lon_max_d_m
    return;
  end
  d_use = max(d, 0.05);
  a = max(p.aeb_decel_mps2, 0.5);
  gap = max(d_use - p.aeb_d_min_m, 0.2);
  vv = max(0.0, v);
  v_obj = max(0.0, vv + rel);
  if v_obj < 0.3
    v_safe = sqrt(max(0.0, 2.0 * a * gap));
    if vv > v_safe
      a_req = min(a, (vv * vv) / (2.0 * gap));
    end
  else
    v_safe = sqrt(v_obj * v_obj + 2.0 * a * gap);
    if vv > v_safe
      a_req = min(a, (vv * vv - v_obj * v_obj) / (2.0 * gap));
    end
  end
  if d_use < p.aeb_d_min_m
    a_req = a;
  end
  a_req = a_req * w;
end
