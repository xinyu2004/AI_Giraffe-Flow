% Pass (low) … in-path / cut-in / ped (high). Cheap, no modes.
function w = gf_plan_obj_weight(lat, heading, is_ped)
  p = gf_plan_cal();
  w = gf_plan_lat_weight(lat);
  if is_ped ~= 0 && abs(lat) < p.lat_aeb_m
    w = max(w, 0.85);
  end
  % heading toward ego lane → bump (cut-in), not a classifier
  if lat * heading < -0.02
    w = min(1.0, w + p.cutin_head_gain * min(abs(heading), 0.5));
  end
end
