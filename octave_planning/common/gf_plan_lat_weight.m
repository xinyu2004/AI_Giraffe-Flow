% 0 far-adjacent … 1 in-path. 1:1 plan_lat_weight().
function w = gf_plan_lat_weight(alat)
  p = gf_plan_cal();
  aa = abs(alat);
  if aa >= p.lat_aeb_m
    w = 0.0;
    return;
  end
  if aa <= p.lat_merge_m
    w = 1.0;
    return;
  end
  w = 1.0 - (aa - p.lat_merge_m) / max(p.lat_aeb_m - p.lat_merge_m, 0.1);
  w = gf_clamp(w, 0.0, 1.0);
end
