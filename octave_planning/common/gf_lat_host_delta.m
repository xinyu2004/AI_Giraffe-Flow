% One host-keep law. 1:1 lat_host_delta.hpp.
% Job: stay on this host (idle, after reg, after LC done). Not a second ctrl law.
% δ = −kψ c1 − atan(k e / v) − atan(L κ). κ from the same poly the path uses (c2 at x=0).
% e/v keeps high-speed e soft (no LKA ky·e yank). Heading kills yaw. Curve holds a bend.
% S-corridor δ is m_lc_path lc_geom, a different reference.
% c3 reserved (κ at x=0 uses c2 only).

function d = gf_lat_host_delta(lane_valid, e_y, c1, c2, c3, v)
  p = gf_plan_cal();
  if nargin < 1
    lane_valid = 0;
  end
  if nargin < 2 || isempty(e_y)
    e_y = 0.0;
  end
  if nargin < 3 || isempty(c1)
    c1 = 0.0;
  end
  if nargin < 4 || isempty(c2)
    c2 = 0.0;
  end
  if nargin < 5 || isempty(c3)
    c3 = 0.0;
  end
  if nargin < 6 || isempty(v)
    v = 0.0;
  end
  if ~gf_lane_usable(lane_valid, e_y, c1)
    d = 0.0;
    return
  end
  e = gf_clamp(e_y, -p.lat_e_sat_m, p.lat_e_sat_m);
  c1c = gf_clamp(c1, -p.lat_c1_sat, p.lat_c1_sat);
  v_e = max(v, p.traj_speed_floor_mps);
  yp = c1c;
  ypp = 2.0 * c2;
  kappa = ypp / ((1.0 + yp * yp) ^ 1.5);
  d = -p.lat_kpsi * c1c - atan(p.lc_reg_k * e / v_e) - atan(p.wheelbase_m * kappa);
  d = gf_clamp(d, -p.lat_max_steer, p.lat_max_steer);
end
