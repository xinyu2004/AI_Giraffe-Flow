% Execute planned δ_ff. 1:1 lat_follow.hpp.
% Layer: actuator rate limit only. Shares last with m_lat_lka / host-keep.
% Enter snaps last in m_ctrl — do not inherit leftover into Hold.

function steer = m_lat_follow(delta_ff, steer_angle_deg)
  if nargin < 1
    delta_ff = 0.0;
  end
  p = gf_plan_cal();
  last = gf_lat_cmd_last();
  cmd = gf_clamp(delta_ff, -p.lat_max_steer, p.lat_max_steer);
  ds = gf_clamp(cmd - last, -p.lat_dsteer_max, p.lat_dsteer_max);
  steer = last + ds;
  gf_lat_cmd_last(steer);
end
