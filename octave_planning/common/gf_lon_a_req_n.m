% Max a_req over ≤obj_n_max targets (take-strict).
function a_req = gf_lon_a_req_n(v, obj, c0)
  a_req = 0.0;
  if nargin < 3 || isempty(c0)
    c0 = 0.0;
  end
  [n, d, rel, lat, len_m, cls, hdg, ped] = gf_plan_obj_unpack(obj);
  if n < 1
    return;
  end
  for k = 1:n
    w = gf_plan_obj_weight(lat(k), hdg(k), ped(k), len_m(k), cls(k), c0);
    ak = gf_lon_a_req(v, 1.0, d(k), rel(k), lat(k), w);
    if ak > a_req
      a_req = ak;
    end
  end
end
