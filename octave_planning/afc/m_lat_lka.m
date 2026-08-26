% AFC lateral LKA — reads gf_plan_cal(). Keep 1:1 with lat_lka.hpp.
% Includes cal lat_dsteer_max (actuator rate) inside LKA — not a host shell.

function steer = m_lat_lka(lane_valid, e_y, c1, steer_angle_deg)
  persistent last_steer
  if isempty(last_steer)
    last_steer = 0.0;
  end
  p = gf_plan_cal();
  if gf_lane_usable(lane_valid, e_y, c1)
    cmd = lat_steer_from_lane(e_y, c1, p);
  else
    cmd = lat_steer_from_ego(steer_angle_deg);
  end
  ds = gf_clamp(cmd - last_steer, -p.lat_dsteer_max, p.lat_dsteer_max);
  steer = last_steer + ds;
  last_steer = steer;
end

function steer = lat_steer_from_lane(e_y, c1, p)
  ky = p.lat_ky;
  e = gf_clamp(e_y, -p.lat_e_sat_m, p.lat_e_sat_m);
  ae = abs(e);
  if ae > p.lat_e_desense_hi_m
    ky = ky * p.lat_ky_scale_hi;
  elseif ae > p.lat_e_desense_lo_m
    ky = ky * p.lat_ky_scale_lo;
  end
  c1c = gf_clamp(c1, -p.lat_c1_sat, p.lat_c1_sat);
  cmd = -ky * e - p.lat_kpsi * c1c;
  steer = gf_clamp(cmd, -p.lat_max_steer, p.lat_max_steer);
end

function steer = lat_steer_from_ego(steer_angle_deg)
  steer = 0.0;
end
