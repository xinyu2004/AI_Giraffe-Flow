% Match moving adjacent traffic (same way, not occupying host). Not a wall.
% Parked / v≈0 skipped. Light still wins via min() with gf_plan_v_reg.
function vi = gf_plan_v_peers(s, v_ego, obj, c0)
  p = gf_plan_cal();
  vi = 1.0e6;
  if nargin < 4 || isempty(c0)
    c0 = 0.0;
  end
  [n, d, rel, lat, len_m, cls, hdg, ped] = gf_plan_obj_unpack(obj);
  if n < 1
    return;
  end
  vv = max(0.0, v_ego);
  half_w = 0.5 * p.lane_width_m;
  for k = 1:n
    if gf_plan_is_reg_stop(cls(k)) > 0.5
      continue;
    end
    if d(k) <= s || d(k) > p.peer_d_max_m
      continue;
    end
    alat = abs(lat(k) - c0);
    if alat <= half_w || alat > p.peer_lat_max_m
      continue;
    end
    w = gf_plan_obj_weight(lat(k), hdg(k), ped(k), len_m(k), cls(k), c0, rel(k));
    if w > 0.5
      continue;
    end
    v_obj = max(0.0, vv + rel(k));
    if v_obj < p.peer_v_min_mps
      continue;
    end
    vi = min(vi, v_obj);
  end
end
