% Internal road-wheel rad → plant [-1,1]. 1:1 plan_cal.hpp steer_rad_to_plant.
% Trajectory.steer / CARLA.steer. Not a second steer law.

function u = gf_steer_rad_to_plant(rad)
  p = gf_plan_cal();
  full = p.steer_max_deg * pi / 180.0;
  u = gf_clamp(rad / max(full, 1.0e-3), -1.0, 1.0);
end
