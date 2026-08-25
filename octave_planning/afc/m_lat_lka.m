% AFC lateral LKA — gold (1:1 with gf_octave_planning/lat_lka.hpp).

function steer = m_lat_lka(lane_valid, e_y, c1, steer_angle_deg)
  if lane_valid
    steer = lat_steer_from_lane(e_y, c1);
  else
    steer = lat_steer_from_ego(steer_angle_deg);
  end
end

function steer = lat_steer_from_lane(e_y, c1)
  ky = 0.35;
  kpsi = 0.80;
  max_steer = 0.55;
  cmd = -ky * e_y - kpsi * c1;
  steer = gf_clamp(cmd, -max_steer, max_steer);
end

function steer = lat_steer_from_ego(steer_angle_deg)
  steer = gf_clamp(steer_angle_deg / 25.0, -1.0, 1.0);
end
