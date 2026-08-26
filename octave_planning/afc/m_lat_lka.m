% AFC lateral LKA — gold (1:1 with gf_octave_planning/lat_lka.hpp).
% Lite: saturate e_y / schedule ky; invalid lane → steer 0 (not ego.steer).

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
  e = gf_clamp(e_y, -1.8, 1.8);
  ae = abs(e);
  if ae > 1.2
    ky = ky * 0.35;
  elseif ae > 0.6
    ky = ky * 0.55;
  end
  c1c = gf_clamp(c1, -0.5, 0.5);
  cmd = -ky * e - kpsi * c1c;
  steer = gf_clamp(cmd, -max_steer, max_steer);
end

function steer = lat_steer_from_ego(steer_angle_deg)
  % Spun / no-lane: do not track ego wheel (was wall-hit amplifier).
  steer = 0.0;
end
