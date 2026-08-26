% Lane usable for control (not BEV). 1:1 with plan_cal.hpp lane_usable().
function u = gf_lane_usable(lane_valid, e_y, c1)
  p = gf_plan_cal();
  u = (lane_valid ~= 0) && (abs(e_y) <= p.lat_ey_invalid_m) && ...
      (abs(c1) <= p.lat_c1_invalid);
end
