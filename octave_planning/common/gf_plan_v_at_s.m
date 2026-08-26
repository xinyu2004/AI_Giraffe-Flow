% Planned speed at station s. obj = n×7 (see gf_plan_obj_unpack). Take-strict.
function vi = gf_plan_v_at_s(s, v_ego, obj, D_see, lane_ok)
  p = gf_plan_cal();
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
  [n, d, rel, lat, ~, ~, hdg, ped] = gf_plan_obj_unpack(obj);
  if n < 1
    return;
  end
  a = max(p.aeb_decel_mps2, 0.5);
  vv = max(0.0, v_ego);
  for k = 1:n
    if d(k) > p.lon_max_d_m
      continue;
    end
    w = gf_plan_obj_weight(lat(k), hdg(k), ped(k));
    if w <= 0.0
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
    v_gap = max(0.0, (gap - p.acc_gap_min_m) / max(p.acc_time_gap_s, 0.2));
    v_lim = min(v_kin, v_gap);
    vi = min(vi, v_lim * w + v_cap * (1.0 - w));
  end
end
