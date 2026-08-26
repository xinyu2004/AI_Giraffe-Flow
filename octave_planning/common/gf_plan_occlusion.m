% Sight cut at near face of in-path / truck. Behind blocker is unknown, not empty.
function D_occ = gf_plan_occlusion(obj)
  p = gf_plan_cal();
  D_occ = p.d_cal_cap_m;
  [n, d, ~, lat, len_m, cls, ~, ~] = gf_plan_obj_unpack(obj);
  if n < 1
    return;
  end
  for k = 1:n
    w = gf_plan_lat_weight(lat(k));
    if w < p.occ_w_min
      continue;
    end
    near = max(0.0, d(k) - 0.5 * len_m(k));
    if cls(k) == p.cls_truck || w > 0.85
      D_occ = min(D_occ, near);
    end
  end
end
