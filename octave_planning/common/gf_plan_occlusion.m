% Cut sight only if the object occupies the host lane (blocks the road in view).
% Adjacent / no overlap: do not cut. Decoupled from brake weight.
function D_occ = gf_plan_occlusion(obj, c0)
  p = gf_plan_cal();
  if nargin < 2 || isempty(c0)
    c0 = 0.0;
  end
  D_occ = p.d_cal_cap_m;
  [n, d, ~, lat, len_m, cls, hdg, ped] = gf_plan_obj_unpack(obj);
  if n < 1
    return;
  end
  for k = 1:n
    occupy = gf_plan_lane_occupy(c0, lat(k), len_m(k), cls(k), hdg(k), ped(k));
    if occupy < p.occ_overlap_min_m
      continue;
    end
    near = max(0.0, d(k) - 0.5 * len_m(k));
    D_occ = min(D_occ, near);
  end
end
