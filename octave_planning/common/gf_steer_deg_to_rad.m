% Ego wheel deg → rad. 1:1 plan_cal.hpp steer_deg_to_rad.

function rad = gf_steer_deg_to_rad(deg)
  rad = deg * pi / 180.0;
end
