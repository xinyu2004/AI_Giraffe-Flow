% obj rows: [d, rel, lat, len, cls, heading, is_ped]. Cap at obj_n_max.
function [n, d, rel, lat, len_m, cls, hdg, ped] = gf_plan_obj_unpack(obj)
  p = gf_plan_cal();
  n = 0;
  d = 0.0;
  rel = 0.0;
  lat = 0.0;
  len_m = 4.5;
  cls = 1.0;
  hdg = 0.0;
  ped = 0.0;
  if nargin < 1 || isempty(obj)
    return;
  end
  if size(obj, 2) < 7 && size(obj, 1) == 7
    obj = obj';
  end
  ncols = size(obj, 2);
  n = min(size(obj, 1), p.obj_n_max);
  if n < 1
    n = 0;
    return;
  end
  d = obj(1:n, 1);
  rel = zeros(n, 1);
  lat = zeros(n, 1);
  len_m = 4.5 * ones(n, 1);
  cls = ones(n, 1);
  hdg = zeros(n, 1);
  ped = zeros(n, 1);
  if ncols >= 2
    rel = obj(1:n, 2);
  end
  if ncols >= 3
    lat = obj(1:n, 3);
  end
  if ncols >= 4
    len_m = max(obj(1:n, 4), 0.5);
  end
  if ncols >= 5
    cls = obj(1:n, 5);
  end
  if ncols >= 6
    hdg = obj(1:n, 6);
  end
  if ncols >= 7
    ped = obj(1:n, 7);
  end
end
