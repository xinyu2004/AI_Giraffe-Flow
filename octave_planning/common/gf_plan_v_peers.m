% Adjacent same-way: stoppable cap, then release if not pointing at host.
% Not occupy, not a wall, not a fixed Δv. Parked / v≈0 skipped.
% First see / pointing in / closer: v_safe immediately.
% Parallel: slew cap up (vis_up_alpha) toward cruise. Hold only at s<=0.5.
% Light still wins via min() with gf_plan_v_reg.
function vi = gf_plan_v_peers(s, v_ego, obj, c0)
  persistent v_hold v_safe_seen had
  p = gf_plan_cal();
  if nargin < 1
    v_hold = 1.0e6;
    v_safe_seen = 1.0e6;
    had = 0;
    vi = 1.0e6;
    return
  end
  if nargin < 4 || isempty(c0)
    c0 = 0.0;
  end
  if isempty(v_hold)
    v_hold = 1.0e6;
    v_safe_seen = 1.0e6;
    had = 0;
  end

  [v_safe, toward, have] = peer_scan(s, v_ego, obj, c0);
  if s <= 0.5
    if ~have
      v_hold = 1.0e6;
      v_safe_seen = 1.0e6;
      had = 0;
    elseif toward || v_safe + 0.5 < v_safe_seen
      v_hold = v_safe;
      v_safe_seen = v_safe;
      had = 1;
    elseif had < 0.5
      v_hold = v_safe;
      v_safe_seen = v_safe;
      had = 1;
    else
      v_hold = gf_plan_vis_slew(p.cruise_v_mps, v_hold, p.vis_up_alpha);
      if v_hold >= p.cruise_v_mps - 0.3
        v_hold = 1.0e6;
      end
      v_safe_seen = v_safe;
      had = 1;
    end
  end

  if v_hold >= 1.0e5
    vi = 1.0e6;
  elseif toward
    vi = min(v_hold, v_safe);
  else
    vi = v_hold;
  end
end

function [v_safe, toward, have] = peer_scan(s, v_ego, obj, c0)
  p = gf_plan_cal();
  v_safe = 1.0e6;
  toward = 0;
  have = 0;
  [n, d, rel, lat, len_m, cls, hdg, ped] = gf_plan_obj_unpack(obj);
  if n < 1
    return
  end
  vv = max(0.0, v_ego);
  half_w = 0.5 * p.lane_width_m;
  a = max(p.aeb_decel_mps2, 0.5);
  for k = 1:n
    if gf_plan_is_reg_stop(cls(k)) > 0.5
      continue
    end
    if d(k) <= s || d(k) > p.peer_d_max_m
      continue
    end
    alat = abs(lat(k) - c0);
    if alat <= half_w || alat > p.peer_lat_max_m
      continue
    end
    w = gf_plan_obj_weight(lat(k), hdg(k), ped(k), len_m(k), cls(k), c0, rel(k));
    if w > 0.5
      continue
    end
    v_obj = max(0.0, vv + rel(k));
    if v_obj < p.peer_v_min_mps
      continue
    end
    have = 1;
    if (lat(k) - c0) * hdg(k) < -0.02
      toward = 1;
    end
    gap = max(0.0, d(k) - s);
    if gap <= p.aeb_d_min_m
      vs = v_obj;
    else
      vs = sqrt(max(0.0, v_obj * v_obj + 2.0 * a * (gap - p.aeb_d_min_m)));
    end
    v_safe = min(v_safe, vs);
  end
end
