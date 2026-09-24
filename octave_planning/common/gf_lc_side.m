% Layer: enter only. 1:1 lc_side.hpp gf_lc_side.
% Host is default. Leave only if a neighbor weight beats host + stay.
% last is unused — Hold/Settle freeze the side, not hysteresis here.
% AFC never calls this (lc_side stays 0).

function [side, emit] = gf_lc_side(q, v, D_see, last)
  if nargin < 2
    v = 0.0;
  end
  if nargin < 3
    D_see = 0.0;
  end
  if nargin < 4
    last = 0;
  end
  p = gf_plan_cal();
  w = gf_lc_weights(q, v, D_see);
  host = w.H + p.lc_stay_m;
  side = 0;
  emit = 0;

  if w.ok_L && w.L > host
    if w.ok_R && w.R > w.L + p.lc_left_bias_m && w.R > host
      side = -1;
    else
      side = 1;
    end
    emit = 1;
    return
  end
  if w.ok_R && w.R > host
    side = -1;
    emit = 1;
  end
end
