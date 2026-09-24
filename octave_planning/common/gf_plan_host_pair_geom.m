% Width-only host pair. Lines may be drawn / used as LC pose when
% we sit on a mark (straddle false). LKA still uses gf_plan_host_pair_ok.
% 1:1 plan_cal.hpp plan_host_pair_geom.

function ok = gf_plan_host_pair_geom(lc0, rc0)
  p = gf_plan_cal();
  ok = 0.0;
  if nargin < 2 || isempty(lc0) || isempty(rc0)
    return;
  end
  w = lc0 - rc0;
  if w < p.host_width_min_m || w > p.host_width_max_m
    return;
  end
  ok = 1.0;
end
