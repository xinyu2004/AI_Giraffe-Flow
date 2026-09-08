% Host L/R C0 may be drawn on BEV even when the corridor is not ours.
% Control only: both lines on their side of ego, plausible width. +y left.
function ok = gf_plan_host_pair_ok(lc0, rc0)
  p = gf_plan_cal();
  ok = 0.0;
  if nargin < 2 || isempty(lc0) || isempty(rc0)
    return;
  end
  w = lc0 - rc0;
  if w < p.host_width_min_m || w > p.host_width_max_m
    return;
  end
  inside = max(p.host_inside_m, 0.05);
  if lc0 < inside || rc0 > -inside
    return;
  end
  ok = 1.0;
end
