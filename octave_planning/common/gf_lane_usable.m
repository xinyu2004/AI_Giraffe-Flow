% Marks exist and offset is not garbage. 1:1 plan_cal.hpp lane_usable().
% c1 is heading error (LKA / curve), not validity. Do not gate on it.
function u = gf_lane_usable(lane_valid, e_y, c1)
  p = gf_plan_cal();
  u = (lane_valid ~= 0) && (abs(e_y) <= p.lat_ey_invalid_m);
end
