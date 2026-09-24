% Rate-limit host-keep. 1:1 lat_lka.hpp.
% Desired δ is gf_lat_host_delta (plan also calls that). This file only slews.
% Direct callers (tests): default v = cruise so 4-arg stays defined.

function steer = m_lat_lka(lane_valid, e_y, c1, steer_angle_deg, v, c2, c3)
  p = gf_plan_cal();
  if nargin < 4
    steer_angle_deg = 0.0;
  end
  if nargin < 5 || isempty(v) || v <= 0.0
    v = p.cruise_v_mps;
  end
  if nargin < 6 || isempty(c2)
    c2 = 0.0;
  end
  if nargin < 7 || isempty(c3)
    c3 = 0.0;
  end
  d = gf_lat_host_delta(lane_valid, e_y, c1, c2, c3, v);
  steer = m_lat_follow(d, steer_angle_deg);
end
